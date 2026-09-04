from fastapi import APIRouter, HTTPException, Response, status

from app.dependencies import CatalogDep, SessionDep, SessionStoreDep, SettingsDep
from app.schemas.matching import MatchingResponse, SearchFilters
from app.schemas.question import Question
from app.schemas.session import (
    AnswerIn,
    BriefResponse,
    SessionCreate,
    SessionCreated,
    SessionMatchRequest,
    SessionView,
)
from app.services.brief import build_brief
from app.services.matching import find_program_matches
from app.services.presenter import build_matching_response
from app.services.profile import answers_to_profile
from app.services.questions import QUESTION_IDS, active_questions, guardian_follow_up
from app.services.sessions import Session

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _view(session: Session) -> SessionView:
    return SessionView(
        session_id=session.id,
        mode=session.mode,
        helper_type=session.helper_type,
        answers=session.answers,
        guardian_follow_up=guardian_follow_up(session.answers),
        created_at=session.created_at,
        expires_at=session.expires_at,
    )


def _match_session(session: Session, catalog, settings) -> MatchingResponse:
    profile = answers_to_profile(session.answers)
    matches = find_program_matches(
        catalog.programs,
        profile,
        filters=SearchFilters(only_currently_open=True),
        include_not_eligible=False,
        limit=settings.match_limit,
    )
    return build_matching_response(matches)


@router.post("", response_model=SessionCreated, status_code=status.HTTP_201_CREATED, summary="세션 생성")
def create_session(body: SessionCreate, store: SessionStoreDep) -> SessionCreated:
    """프론트엔드 `createSession(mode)`. 로그인 없이 세션 코드만 발급한다."""
    session = store.create(mode=body.mode, helper_type=body.helper_type)
    return SessionCreated(session_id=session.id, mode=session.mode, expires_at=session.expires_at)


@router.get("/{session_id}", response_model=SessionView, summary="세션 조회")
def read_session(session: SessionDep) -> SessionView:
    return _view(session)


@router.get("/{session_id}/questions", response_model=list[Question], summary="현재 답변 기준 활성 질문")
def session_questions(session: SessionDep) -> list[Question]:
    """앞선 답변에 따라 건너뛰는 후속 질문(자녀 연락 시점, 식사 준비 가능 여부)을 제외한 목록."""
    return active_questions(session.answers)


@router.put("/{session_id}/answers/{question_id}", response_model=SessionView, summary="답변 저장")
def save_answer(question_id: str, body: AnswerIn, session: SessionDep, store: SessionStoreDep) -> SessionView:
    """프론트엔드 `saveAnswer(sessionId, questionId, value)`. 같은 질문을 다시 보내면 덮어쓴다."""
    if question_id not in QUESTION_IDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"알 수 없는 질문입니다: {question_id}")
    updated = store.set_answer(session.id, question_id, body.value)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션이 만료되었습니다.")
    return _view(updated)


@router.post("/{session_id}/matches", response_model=MatchingResponse, summary="세션 맞춤 추천")
def match_session(
    session: SessionDep,
    store: SessionStoreDep,
    catalog: CatalogDep,
    settings: SettingsDep,
    body: SessionMatchRequest | None = None,
) -> MatchingResponse:
    """프론트엔드 `getMatches(sessionId, answers)`. 답변을 프로필로 변환해 추천 카드를 만든다."""
    if body is not None and body.answers:
        session = store.merge_answers(session.id, body.answers) or session
    return _match_session(session, catalog, settings)


@router.get("/{session_id}/brief", response_model=BriefResponse, summary="주민센터 전달 안내문")
def session_brief(session: SessionDep, catalog: CatalogDep, settings: SettingsDep) -> BriefResponse:
    """방문 시 화면으로 보여주거나 보호자에게 공유할 안내문. 계좌번호는 담지 않는다."""
    result = _match_session(session, catalog, settings)
    return BriefResponse(text=build_brief(session.answers, result.benefits, result.needs_guardian_input))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="세션 삭제")
def delete_session(session: SessionDep, store: SessionStoreDep) -> Response:
    store.delete(session.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
