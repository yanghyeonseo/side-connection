"""로그인 없는 세션 저장소.

개인정보 최소 보관 원칙에 따라 메모리에만 두고 TTL이 지나면 지운다.
여러 인스턴스로 확장할 때는 같은 인터페이스로 Redis 등에 옮기면 된다.
"""

import secrets
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.schemas.session import AnswerValue

CASE_CODE_DIGITS = 8


class SessionStoreFull(RuntimeError):
    """세션 상한 도달. 잠시 후 다시 시도해야 한다."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Session:
    id: str
    case_code: str
    mode: str
    helper_type: str | None
    created_at: datetime
    expires_at: datetime
    answers: dict[str, AnswerValue] = field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return _now() >= self.expires_at


def _snapshot(session: Session | None) -> Session | None:
    """락 밖으로 내보낼 복사본. 원본 answers가 동시에 바뀌어도 읽기가 안전하다."""
    return None if session is None else replace(session, answers=dict(session.answers))


class SessionStore:
    def __init__(self, ttl: timedelta, max_sessions: int = 20_000):
        self._ttl = ttl
        self._max_sessions = max_sessions
        self._items: dict[str, Session] = {}
        self._by_case_code: dict[str, str] = {}
        self._lock = Lock()

    def create(self, mode: str, helper_type: str | None = None) -> Session:
        now = _now()
        with self._lock:
            self._purge_locked()
            if len(self._items) >= self._max_sessions:
                raise SessionStoreFull
            session = Session(
                id=str(uuid.uuid4()),
                case_code=self._new_case_code_locked(),
                mode=mode,
                helper_type=helper_type,
                created_at=now,
                expires_at=now + self._ttl,
            )
            self._items[session.id] = session
            self._by_case_code[session.case_code] = session.id
            return _snapshot(session)

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return _snapshot(self._get_locked(session_id))

    def get_by_case_code(self, case_code: str) -> Session | None:
        with self._lock:
            session_id = self._by_case_code.get(case_code)
            return _snapshot(self._get_locked(session_id)) if session_id else None

    def set_answer(self, session_id: str, question_id: str, value: AnswerValue) -> Session | None:
        with self._lock:
            session = self._get_locked(session_id)
            if session is None:
                return None
            session.answers[question_id] = value
            return _snapshot(session)

    def merge_answers(self, session_id: str, answers: dict[str, AnswerValue]) -> Session | None:
        with self._lock:
            session = self._get_locked(session_id)
            if session is None:
                return None
            session.answers.update(answers)
            return _snapshot(session)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            session = self._items.pop(session_id, None)
            if session is None:
                return False
            self._by_case_code.pop(session.case_code, None)
            return True

    def purge_expired(self) -> int:
        with self._lock:
            return self._purge_locked()

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._by_case_code.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def _get_locked(self, session_id: str) -> Session | None:
        session = self._items.get(session_id)
        if session is not None and session.expired:
            self._remove_locked(session)
            return None
        return session

    def _new_case_code_locked(self) -> str:
        while True:
            code = "".join(secrets.choice("0123456789") for _ in range(CASE_CODE_DIGITS))
            if code not in self._by_case_code:
                return code

    def _remove_locked(self, session: Session) -> None:
        self._items.pop(session.id, None)
        self._by_case_code.pop(session.case_code, None)

    def _purge_locked(self) -> int:
        expired = [session for session in self._items.values() if session.expired]
        for session in expired:
            self._remove_locked(session)
        return len(expired)
