"""사례번호로 여는 두 화면을 만든다.

- 행정 확인(AdminCase): 주민센터·상담원이 전화로 사례번호를 받고 여는 사전상담 요약.
- 보호자 보완(HelperCase): 어르신이 '잘 모르겠어요'로 넘긴 항목을 보호자가 대신 채우는 폼.
"""

from zoneinfo import ZoneInfo

from app.schemas.session import AdminCase, AnswerValue, HelperField
from app.services.questions import QUESTIONS, UNKNOWN_ANSWER, active_questions
from app.services.sessions import Session

KST = ZoneInfo("Asia/Seoul")
UNANSWERED = "미입력 (확인 필요)"

MULTI_QUESTION_IDS = frozenset(q.id for q in QUESTIONS if q.multiple)
_QUESTION_OPTIONS = {q.id: q.options for q in QUESTIONS}

# 질문을 보호자 눈높이 문구로 바꾼 보완 폼 정의. options가 없으면 텍스트 입력.
# 선택지가 있는 질문은 원래 선택지를 그대로 써야 매칭 엔진이 답을 해석할 수 있다.
HELPER_FIELD_OVERRIDES: dict[str, HelperField] = {
    "birthYear": HelperField(id="birthYear", label="어르신 출생 연도", description="예: 1945", input="number"),
    "area": HelperField(id="area", label="사시는 지역", description="시·군·구까지 적어주세요. 예: 서울특별시 종로구", input="text"),
    "receiving": HelperField(
        id="receiving",
        label="현재 받는 복지급여",
        description="아는 것을 모두 골라주세요.",
        options=_QUESTION_OPTIONS["receiving"],
        multiple=True,
    ),
    "need": HelperField(
        id="need",
        label="가장 필요한 도움",
        description="해당하는 것을 모두 골라주세요.",
        options=_QUESTION_OPTIONS["need"],
        multiple=True,
    ),
    "income": HelperField(
        id="income",
        label="한 달에 들어오는 돈",
        description="연금, 일, 가족 지원을 모두 더한 대략의 금액이에요.",
        options=_QUESTION_OPTIONS["income"],
    ),
}

# 주거가 전세·월세일 때만 의미 있는 추가 항목. 질문 흐름에는 없고 보호자에게만 묻는다.
HOUSING_DETAIL_FIELD = HelperField(
    id="housingDetail",
    label="집 계약 정보",
    description="보증금과 월세를 아는 대로 적어주세요. 예: 보증금 500, 월세 25",
    input="text",
)

ALLOWED_HELPER_IDS = frozenset(q.id for q in QUESTIONS) | {HOUSING_DETAIL_FIELD.id}


def _is_missing(answers: dict[str, AnswerValue], question_id: str) -> bool:
    value = answers.get(question_id)
    if value is None or value == UNKNOWN_ANSWER:
        return True
    if isinstance(value, list):
        return all(item == UNKNOWN_ANSWER for item in value)
    return False


def helper_missing_fields(session: Session) -> list[HelperField]:
    """보호자가 채울 항목. 비어 있거나 '잘 모르겠어요'인 활성 질문만 고른다."""
    fields: list[HelperField] = []
    for question in active_questions(session.answers):
        if not _is_missing(session.answers, question.id):
            continue
        override = HELPER_FIELD_OVERRIDES.get(question.id)
        if override is not None:
            fields.append(override.model_copy())
        else:
            fields.append(
                HelperField(
                    id=question.id,
                    label=question.title,
                    description=question.description,
                    input=question.input,
                    options=question.options,
                    multiple=bool(question.multiple),
                )
            )
    if session.answers.get("housing") == "전세·월세예요" and _is_missing(session.answers, "housingDetail"):
        fields.append(HOUSING_DETAIL_FIELD.model_copy())
    return fields


def merge_helper_answers(values: dict[str, str]) -> dict[str, AnswerValue]:
    """보호자 입력을 세션 답변 형식으로 바꾼다. 알 수 없는 키는 버린다."""
    merged: dict[str, AnswerValue] = {}
    for field_id, raw in values.items():
        text = raw.strip()
        if field_id not in ALLOWED_HELPER_IDS or not text:
            continue
        if field_id in MULTI_QUESTION_IDS:
            merged[field_id] = [item.strip() for item in text.split(",") if item.strip()]
        else:
            merged[field_id] = text
    return merged


def _answer_text(answers: dict[str, AnswerValue], key: str) -> str | None:
    value = answers.get(key)
    if isinstance(value, list):
        items = [item for item in value if item != UNKNOWN_ANSWER]
        return ", ".join(items) if items else None
    if isinstance(value, str) and value != UNKNOWN_ANSWER:
        return value
    return None


def _address_line(answers: dict[str, AnswerValue]) -> str:
    area = _answer_text(answers, "area")
    if area is None:
        return UNANSWERED
    if _answer_text(answers, "areaDetail"):
        return f"{area} (상세 주소는 본인 확인 후 열람)"
    return area


def _family_line(answers: dict[str, AnswerValue]) -> str:
    children = _answer_text(answers, "children")
    if children is None:
        return UNANSWERED
    last_contact = _answer_text(answers, "lastContact")
    return f"{children} (마지막 연락: {last_contact})" if last_contact else children


def _needs_line(answers: dict[str, AnswerValue]) -> str:
    needs = _answer_text(answers, "need")
    mobility = _answer_text(answers, "mobility")
    parts = [part for part in (needs, f"식사 준비: {mobility}" if mobility else None) if part]
    return " / ".join(parts) if parts else UNANSWERED


def _identity_line(answers: dict[str, AnswerValue]) -> str:
    id_card = _answer_text(answers, "idCard")
    visit = _answer_text(answers, "visit")
    parts = [
        f"신분증·통장: {id_card}" if id_card else None,
        f"주민센터 방문: {visit}" if visit else None,
    ]
    joined = " / ".join(part for part in parts if part)
    return joined or UNANSWERED


def build_admin_case(session: Session, recommended_benefits: list[str], note: str) -> AdminCase:
    """세션 진술을 행정 확인 화면 필드로 정리한다. 계좌번호 등 금융정보는 다루지 않는다."""
    answers = session.answers
    income = _answer_text(answers, "income")
    receiving = _answer_text(answers, "receiving")
    return AdminCase(
        case_code=session.case_code,
        created_at=session.created_at.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
        address=_address_line(answers),
        household=_answer_text(answers, "household") or UNANSWERED,
        income_band=f"월 소득 {income} (본인 진술)" if income else UNANSWERED,
        public_benefits=f"{receiving} (본인 진술)" if receiving else UNANSWERED,
        family_support=_family_line(answers),
        needs=_needs_line(answers),
        identity_and_account=_identity_line(answers),
        recommended_benefits=recommended_benefits,
        note=note,
    )
