"""질문 답변 → 추천 엔진 프로필 변환. `frontend/src/api/client.ts`의 `answersToProfile` 포팅.

조건표를 그대로 묻지 않고 상황을 물은 뒤, 여기서 조건 코드로 옮긴다.
"""

from datetime import date

from app.schemas.profile import BeneficiaryProfile
from app.schemas.session import AnswerValue
from app.services.questions import UNKNOWN_ANSWER

NEED_CATEGORIES: dict[str, list[str]] = {
    "생활비가 부담돼요": ["LIVING"],
    "병원비가 걱정돼요": ["MEDICAL"],
    "식사·혼자 생활": ["MEAL", "CARE"],
    "외출·이동": ["MOBILITY"],
    "집 문제": ["HOUSING"],
    "혼자 있을 때 안전": ["SAFETY"],
}


def string_answer(answers: dict[str, AnswerValue], key: str) -> str | None:
    value = answers.get(key)
    return value if isinstance(value, str) and value != UNKNOWN_ANSWER else None


def list_answer(answers: dict[str, AnswerValue], key: str) -> list[str]:
    value = answers.get(key)
    return [item for item in value if item != UNKNOWN_ANSWER] if isinstance(value, list) else []


def _age_from_birth_year(raw: str | None) -> int | None:
    current_year = date.today().year
    try:
        birth_year = int(raw) if raw is not None else None
    except ValueError:
        return None
    if birth_year is None or not (1900 < birth_year <= current_year):
        return None
    return current_year - birth_year


def answers_to_profile(answers: dict[str, AnswerValue]) -> BeneficiaryProfile:
    household = string_answer(answers, "household")
    receiving = list_answer(answers, "receiving")
    needs = list_answer(answers, "need")
    mobility = string_answer(answers, "mobility")
    housing = string_answer(answers, "housing")
    visit = string_answer(answers, "visit")
    children = string_answer(answers, "children") or ""

    categories = list(dict.fromkeys(item for need in needs for item in NEED_CATEGORIES.get(need, [])))
    income_types: list[str] = []
    tags: list[str] = []

    if "기초연금" in receiving:
        income_types.append("BASIC_PENSION_RECIPIENT")
    if "생계비 지원" in receiving:
        income_types.append("BASIC_LIVELIHOOD_ANY")
    if "병원비 지원" in receiving:
        income_types.append("MEDICAL_AID_RECIPIENT")
    if "집세 지원" in receiving:
        income_types.append("BASIC_LIVELIHOOD_ANY")

    if household == "혼자 살아요":
        tags += ["LIVING_ALONE", "SOCIAL_ISOLATION"]
    if "끊겼어요" in children or "없어요" in children:
        tags.append("FAMILY_SUPPORT_ABSENT")
    if "식사·혼자 생활" in needs:
        tags += ["MEAL_PREP_DIFFICULTY", "DAILY_LIVING_DIFFICULTY"]
    if "외출·이동" in needs or visit == "못 가요":
        tags.append("MOBILITY_DIFFICULTY")
    if "병원비가 걱정돼요" in needs:
        tags.append("MEDICAL_EXPENSE_BURDEN")
    if "혼자 있을 때 안전" in needs:
        tags.append("EMERGENCY_SAFETY_RISK")
    if housing == "제 집이에요":
        tags.append("HOME_OWNER")
    if housing == "전세·월세예요":
        tags.append("RENT_BURDEN")
    if housing == "자녀·친척 집이에요":
        tags.append("HOUSING_INSTABILITY")

    if mobility == "못 해요":
        assistance_need = ["HIGH"]
    elif mobility == "힘들지만 해요":
        assistance_need = ["MEDIUM"]
    else:
        assistance_need = ["LOW"]

    return BeneficiaryProfile(
        age=_age_from_birth_year(string_answer(answers, "birthYear")),
        region=string_answer(answers, "area"),
        living_alone=(household == "혼자 살아요") if household else None,
        basic_livelihood_recipient="생계비 지원" in receiving,
        medical_aid_recipient="병원비 지원" in receiving,
        basic_pension_recipient="기초연금" in receiving,
        income_information_complete=False,
        income_types=income_types,
        needs=categories,
        assistance_need=assistance_need,
        tags=tags,
    )
