"""로그인 없는 세션 저장소.

개인정보 최소 보관 원칙에 따라 메모리에만 두고 TTL이 지나면 지운다.
여러 인스턴스로 확장할 때는 같은 인터페이스로 Redis 등에 옮기면 된다.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.schemas.session import AnswerValue


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Session:
    id: str
    mode: str
    helper_type: str | None
    created_at: datetime
    expires_at: datetime
    answers: dict[str, AnswerValue] = field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return _now() >= self.expires_at


class SessionStore:
    def __init__(self, ttl: timedelta):
        self._ttl = ttl
        self._items: dict[str, Session] = {}
        self._lock = Lock()

    def create(self, mode: str, helper_type: str | None = None) -> Session:
        now = _now()
        session = Session(
            id=str(uuid.uuid4()),
            mode=mode,
            helper_type=helper_type,
            created_at=now,
            expires_at=now + self._ttl,
        )
        with self._lock:
            self._purge_locked()
            self._items[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._items.get(session_id)
            if session is not None and session.expired:
                del self._items[session_id]
                return None
            return session

    def set_answer(self, session_id: str, question_id: str, value: AnswerValue) -> Session | None:
        with self._lock:
            session = self._items.get(session_id)
            if session is None or session.expired:
                return None
            session.answers[question_id] = value
            return session

    def merge_answers(self, session_id: str, answers: dict[str, AnswerValue]) -> Session | None:
        with self._lock:
            session = self._items.get(session_id)
            if session is None or session.expired:
                return None
            session.answers.update(answers)
            return session

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._items.pop(session_id, None) is not None

    def purge_expired(self) -> int:
        with self._lock:
            return self._purge_locked()

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def _purge_locked(self) -> int:
        expired = [session_id for session_id, session in self._items.items() if session.expired]
        for session_id in expired:
            del self._items[session_id]
        return len(expired)
