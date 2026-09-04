"""상황 입력 질문 흐름. `frontend/src/data/questions.ts`와 `App.tsx`의 분기 규칙을 그대로 둔다."""

from app.schemas.question import Question
from app.schemas.session import AnswerValue

UNKNOWN_ANSWER = "잘 모르겠어요"

QUESTIONS: list[Question] = [
    Question(id="birthYear", title="몇 년에 태어나셨어요?", description="정확히 기억나지 않으면 대략 알려주세요.", input="number"),
    Question(id="area", title="지금 어디에 살고 계세요?", description="시·군·구까지만 알려주셔도 돼요.", input="text"),
    Question(id="household", title="지금 집에 누구와 살고 계세요?", options=["혼자 살아요", "배우자와 살아요", "자녀·손주와 살아요", "다른 사람과 살아요"]),
    Question(id="children", title="아드님·따님이 계세요?", options=["네, 연락도 잘 돼요", "있는데 연락이 잘 안 돼요", "있는데 아예 끊겼어요", "없어요"]),
    Question(id="lastContact", title="마지막으로 연락한 게 언제쯤이에요?", options=["1년 안", "1~3년", "3년 넘게", "기억 안 나요"]),
    Question(id="receiving", title="지금 나라에서 받는 것이 있으세요?", description="해당하는 것을 모두 눌러 주세요.", options=["기초연금", "생계비 지원", "병원비 지원", "집세 지원", "없어요"], multiple=True),
    Question(id="need", title="지금 가장 필요한 도움은 무엇인가요?", description="여러 개 골라도 괜찮아요.", options=["생활비가 부담돼요", "병원비가 걱정돼요", "식사·혼자 생활", "외출·이동", "집 문제", "혼자 있을 때 안전"], multiple=True),
    Question(id="income", title="한 달에 들어오는 돈은 얼마쯤이에요?", description="연금, 일해서 번 돈, 가족이 주는 돈을 모두 더해요.", options=["30만 원 아래", "30~60만 원", "60~100만 원", "100만 원 넘게"]),
    Question(id="housing", title="지금 사시는 집은 어떤 집인가요?", options=["제 집이에요", "전세·월세예요", "자녀·친척 집이에요", "잘 모르겠어요"]),
    Question(id="mobility", title="혼자 장 보고 식사 준비하는 게 어떠세요?", options=["혼자 다 해요", "힘들지만 해요", "못 해요"]),
    Question(id="idCard", title="신분증과 본인 통장이 있으세요?", options=["둘 다 있어요", "신분증만 있어요", "통장만 있어요", "둘 다 없어요"]),
    Question(id="visit", title="주민센터에 직접 가실 수 있으세요?", options=["혼자 갈 수 있어요", "누가 같이 가주면요", "못 가요"]),
]

QUESTION_IDS = frozenset(question.id for question in QUESTIONS)


def is_active(question_id: str, answers: dict[str, AnswerValue]) -> bool:
    """앞선 답변에 따라 건너뛰는 후속 질문을 판정한다."""
    if question_id == "lastContact":
        children = answers.get("children")
        return isinstance(children, str) and children not in ("없어요", "네, 연락도 잘 돼요")
    if question_id == "mobility":
        need = answers.get("need")
        return isinstance(need, list) and "식사·혼자 생활" in need
    return True


def active_questions(answers: dict[str, AnswerValue]) -> list[Question]:
    return [question for question in QUESTIONS if is_active(question.id, answers)]


def guardian_follow_up(answers: dict[str, AnswerValue]) -> list[str]:
    """'잘 모르겠어요'로 넘긴 질문 ID. 보호자가 보완할 목록이 된다."""
    return [question_id for question_id, value in answers.items() if value == UNKNOWN_ANSWER]
