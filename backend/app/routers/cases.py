"""사례번호(caseCode)로 여는 행정 확인·보호자 보완 API.

세션 ID는 본인 기기에만 있고, 사례번호는 전화·문자·링크로 전달된다.
사례번호는 8자리 능력 토큰이므로 IP별 조회 제한으로 무차별 대입을 막고,
개인정보가 담긴 응답은 중간 캐시에 남지 않게 한다.
"""

from collections import OrderedDict
from threading import Lock

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.dependencies import CatalogDep, SessionStoreDep, SettingsDep
from app.schemas.session import AdminCase, HelperAnswersIn, HelperCase
from app.services import ai
from app.services.cases import build_admin_case, helper_missing_fields, merge_helper_answers
from app.services.recommend import answers_cache_key, recommend_for_answers
from app.services.sessions import Session, SessionStore

router = APIRouter(tags=["cases"])

ADMIN_BENEFIT_LIMIT = 5

# 답변이 그대로면 상담원 화면을 새로고침해도 AI 메모를 다시 만들지 않는다.
_NOTE_CACHE_LIMIT = 256
_note_cache: OrderedDict[tuple, str] = OrderedDict()
_note_lock = Lock()


def _rate_limited_session(request: Request, store: SessionStore, case_code: str) -> Session:
    limiter = request.app.state.case_lookup_limiter
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.allow(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
        )
    session = store.get_by_case_code(case_code)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사례를 찾을 수 없거나 만료되었습니다.",
        )
    return session


def _counselor_note(settings, session: Session, benefit_names: list[str]) -> str:
    key = (session.case_code, answers_cache_key(session.answers))
    with _note_lock:
        cached = _note_cache.get(key)
        if cached is not None:
            _note_cache.move_to_end(key)
            return cached
    note = ai.counselor_note(settings, session.answers, benefit_names)
    with _note_lock:
        _note_cache[key] = note
        while len(_note_cache) > _NOTE_CACHE_LIMIT:
            _note_cache.popitem(last=False)
    return note


@router.get("/admin/cases/{case_code}", response_model=AdminCase, summary="행정 확인 화면")
def read_admin_case(
    case_code: str,
    request: Request,
    response: Response,
    store: SessionStoreDep,
    catalog: CatalogDep,
    settings: SettingsDep,
) -> AdminCase:
    """주민센터·상담원이 사례번호로 여는 사전상담 요약. 진술 기반임을 명시한다."""
    response.headers["Cache-Control"] = "no-store"
    session = _rate_limited_session(request, store, case_code)
    result = recommend_for_answers(session.answers, catalog, settings)
    benefit_names = [benefit.name for benefit in result.benefits[:ADMIN_BENEFIT_LIMIT]]
    note = _counselor_note(settings, session, benefit_names)
    return build_admin_case(session, benefit_names, note)


@router.get("/helper/cases/{case_code}", response_model=HelperCase, summary="보호자 보완 항목")
def read_helper_case(
    case_code: str, request: Request, response: Response, store: SessionStoreDep
) -> HelperCase:
    """어르신이 채우지 못한 항목만 돌려준다. 이미 답한 내용은 노출하지 않는다."""
    response.headers["Cache-Control"] = "no-store"
    session = _rate_limited_session(request, store, case_code)
    return HelperCase(case_code=session.case_code, missing_fields=helper_missing_fields(session))


@router.put(
    "/helper/cases/{case_code}/answers",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="보호자 답변 저장",
)
def save_helper_answers(
    case_code: str, body: HelperAnswersIn, request: Request, store: SessionStoreDep
) -> None:
    """빈 항목만 채울 수 있다. 어르신이 이미 답한 내용은 보호자가 덮어쓰지 못한다."""
    session = _rate_limited_session(request, store, case_code)
    allowed = {field.id for field in helper_missing_fields(session)}
    merged = {key: value for key, value in merge_helper_answers(body.answers).items() if key in allowed}
    if not merged:
        if body.answers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="저장할 수 있는 항목이 없습니다. 빈 항목만 채울 수 있어요.",
            )
        return
    store.merge_answers(session.id, merged)
