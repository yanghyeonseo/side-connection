from fastapi import APIRouter

from app.schemas.question import Question
from app.services.questions import QUESTIONS

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=list[Question], summary="전체 질문 목록")
def list_questions() -> list[Question]:
    """분기 규칙이 적용되지 않은 전체 질문. 세션별 활성 질문은 `/sessions/{id}/questions`."""
    return QUESTIONS
