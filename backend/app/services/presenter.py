"""추천 판정 결과를 프론트엔드 카드(`Benefit`)로 바꾼다. `client.ts`의 `toBenefit` 포팅.

"확실히 받을 수 있다"는 표현은 쓰지 않는다. 신청해볼 수 있어요 / 확인이 필요해요 두 가지만 쓴다.
"""

from app.schemas.matching import Benefit, ConditionStatus, MatchingResponse, MatchStatus, ProgramMatch

CATEGORY_LABELS = {
    "CARE": "일상 돌봄",
    "HOUSING": "주거",
    "LIVING": "생활비",
    "MEAL": "식사",
    "MEDICAL": "의료",
    "MOBILITY": "이동",
    "SAFETY": "안전",
}

TAG_LIKELY = "신청해볼 수 있어요"
TAG_NEEDS_CONFIRMATION = "확인이 필요해요"


def match_reason(match: ProgramMatch) -> str:
    needs = [CATEGORY_LABELS.get(item, item) for item in match.matched_needs]
    if needs:
        return f"말씀하신 {'·'.join(needs)} 도움이 이 사업의 지원내용과 맞을 수 있어요."
    matched = next(
        (item for item in match.conditions if item.status is ConditionStatus.MATCHED and item.key != "region"),
        None,
    )
    return matched.detail if matched else "입력하신 상황에서 신청 가능성을 확인해 볼 만한 사업이에요."


def to_benefit(match: ProgramMatch) -> Benefit:
    program = match.program
    unknown = [item.detail for item in match.conditions if item.status is ConditionStatus.UNKNOWN]
    needs_check = [item for item in [*unknown, *match.confirmation_items[:2]] if item]

    return Benefit(
        id=program.id,
        name=program.name,
        tag=TAG_LIKELY if match.status is MatchStatus.LIKELY else TAG_NEEDS_CONFIRMATION,
        summary=program.summary,
        amount=" · ".join(program.benefits),
        reason=match_reason(match),
        location=f"{program.application.organization} · {program.application.method}",
        needs_check=" / ".join(needs_check) if needs_check else None,
        supplies=program.required_documents,
        contact=program.application.contact,
        source_url=program.source.url,
        eligibility_status=match.status,
    )


def build_matching_response(matches: list[ProgramMatch], *, guardian_input_limit: int = 3) -> MatchingResponse:
    labels: list[str] = []
    for match in matches:
        for item in match.conditions:
            if item.status is ConditionStatus.UNKNOWN and item.label not in labels:
                labels.append(item.label)
    return MatchingResponse(
        benefits=[to_benefit(match) for match in matches],
        needs_guardian_input=labels[:guardian_input_limit],
    )
