"""사례번호(caseCode)로 여는 행정 확인·보호자 보완 API.

세션 ID는 본인 기기에만 있고, 사례번호는 전화·문자·링크로 전달된다.
"""

from fastapi import APIRouter, HTTPException, status

from app.dependencies import CatalogDep, SessionStoreDep, SettingsDep
from app.schemas.session import AdminCase, HelperAnswersIn, HelperCase
from app.services import ai
from app.services.cases import build_admin_case, helper_missing_fields, merge_helper_answers
from app.services.recommend import recommend_for_answers
from app.services.sessions import Session, SessionStore

router = APIRouter(tags=["cases"])

ADMIN_BENEFIT_LIMIT = 5


def _session_by_case_code(store: SessionStore, case_code: str) -> Session:
    session = store.get_by_case_code(case_code)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사례를 찾을 수 없거나 만료되었습니다.",
        )
    return session


@router.get("/admin/cases/{case_code}", response_model=AdminCase, summary="행정 확인 화면")
def read_admin_case(
    case_code: str, store: SessionStoreDep, catalog: CatalogDep, settings: SettingsDep
) -> AdminCase:
    """주민센터·상담원이 사례번호로 여는 사전상담 요약. 진술 기반임을 명시한다."""
    session = _session_by_case_code(store, case_code)
    result = recommend_for_answers(session.answers, catalog, settings)
    benefit_names = [benefit.name for benefit in result.benefits[:ADMIN_BENEFIT_LIMIT]]
    note = ai.counselor_note(settings, session.answers, benefit_names)
    return build_admin_case(session, benefit_names, note)


@router.get("/helper/cases/{case_code}", response_model=HelperCase, summary="보호자 보완 항목")
def read_helper_case(case_code: str, store: SessionStoreDep) -> HelperCase:
    """어르신이 채우지 못한 항목만 돌려준다. 이미 답한 내용은 노출하지 않는다."""
    session = _session_by_case_code(store, case_code)
    return HelperCase(case_code=session.case_code, missing_fields=helper_missing_fields(session))


@router.put(
    "/helper/cases/{case_code}/answers",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="보호자 답변 저장",
)
def save_helper_answers(case_code: str, body: HelperAnswersIn, store: SessionStoreDep) -> None:
    session = _session_by_case_code(store, case_code)
    merged = merge_helper_answers(body.answers)
    if merged:
        store.merge_answers(session.id, merged)
