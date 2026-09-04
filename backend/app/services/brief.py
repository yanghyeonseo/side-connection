"""주민센터 전달용 안내문. `frontend/src/App.tsx`의 `brief()`와 같은 형식.

계좌번호는 본문에 넣지 않는다. 방문 시 직접 제시한다.
"""

from app.schemas.matching import Benefit
from app.schemas.session import AnswerValue
from app.services.profile import string_answer

TITLE = "[곁에 서비스 신청 안내]"


def build_brief(
    answers: dict[str, AnswerValue],
    benefits: list[Benefit],
    needs_guardian_input: list[str] | None = None,
) -> str:
    area = string_answer(answers, "area") or "거주지"
    household = string_answer(answers, "household")
    children = string_answer(answers, "children")

    lines = [TITLE, "", f"안녕하세요. {area}에 사시는 어르신입니다."]
    if household:
        lines.append(household)
    if children == "있는데 아예 끊겼어요":
        lines.append("자녀와 연락이 끊긴 상태입니다.")

    lines += ["", "다음 지원을 상담받고 싶습니다."]
    lines += [f"{index}. {benefit.name}" for index, benefit in enumerate(benefits, start=1)]

    if needs_guardian_input:
        lines += ["", f"확인이 필요한 것: {', '.join(needs_guardian_input)}"]

    lines += ["", "준비물과 자격을 확인 부탁드립니다.", "정확한 자격은 주민센터에서 확인이 필요합니다."]
    return "\n".join(lines)
