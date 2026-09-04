"""프로필 기반 추천 판정. `frondend/welfare-search.js`의 `evaluateProgram`/`findProgramMatches` 포팅.

원칙: 명확한 불일치만 탈락시키고, 정보가 없거나 지자체별로 다른 조건은
`NEEDS_CONFIRMATION`으로 남긴다. 자격의 최종 확정은 담당기관이 한다.
"""

from collections.abc import Iterable

from app.schemas.matching import ConditionStatus, MatchCondition, MatchStatus, ProgramMatch, SearchFilters
from app.schemas.profile import BeneficiaryProfile
from app.schemas.program import WelfareProgram
from app.services.search import NATIONWIDE, regions_compatible, search_programs

STATUS_RANK = {
    MatchStatus.LIKELY: 0,
    MatchStatus.NEEDS_CONFIRMATION: 1,
    MatchStatus.NOT_ELIGIBLE: 2,
}

SCORE_PER_MATCHED_NEED = 18
SCORE_PER_MATCHED_TAG = 7
SCORE_ASSISTANCE_MATCH = 10
SCORE_CONDITION_MATCHED = 12
SCORE_CONDITION_UNKNOWN = -3
SCORE_CONDITION_NOT_MATCHED = -50


def _condition(key: str, label: str, status: ConditionStatus, detail: str, hard: bool = False) -> MatchCondition:
    return MatchCondition(key=key, label=label, status=status, detail=detail, hard=hard)


def evaluate_age(program: WelfareProgram, profile: BeneficiaryProfile) -> MatchCondition:
    min_age = program.eligibility.min_age
    max_age = program.eligibility.max_age
    if min_age is None and max_age is None:
        return _condition("age", "연령", ConditionStatus.NOT_APPLICABLE, "연령 제한 없음")
    if profile.age is None:
        low = min_age if min_age is not None else 0
        high = max_age if max_age is not None else "제한 없음"
        return _condition("age", "연령", ConditionStatus.UNKNOWN, f"연령 확인 필요 ({low}~{high}세)", True)
    matched = (min_age is None or profile.age >= min_age) and (max_age is None or profile.age <= max_age)
    if matched:
        return _condition("age", "연령", ConditionStatus.MATCHED, f"만 {profile.age}세로 연령 범위 충족", True)
    return _condition("age", "연령", ConditionStatus.NOT_MATCHED, f"만 {profile.age}세는 사업 연령 범위 밖", True)


def evaluate_region(program: WelfareProgram, profile: BeneficiaryProfile) -> MatchCondition:
    coverage = program.coverage
    if any(item in NATIONWIDE for item in coverage):
        return _condition("region", "지역", ConditionStatus.MATCHED, "전국 사업", True)
    if not profile.region:
        return _condition("region", "지역", ConditionStatus.UNKNOWN, f"거주지 확인 필요 ({', '.join(coverage)})", True)
    matched = regions_compatible(coverage, profile.region)
    if matched is None:
        return _condition("region", "지역", ConditionStatus.UNKNOWN, "전국 틀 안에서 지자체·공고별 시행 여부 확인", True)
    if matched:
        return _condition("region", "지역", ConditionStatus.MATCHED, f"{profile.region} 대상 가능", True)
    return _condition("region", "지역", ConditionStatus.NOT_MATCHED, f"{profile.region}은 지원 지역과 불일치", True)


def evaluate_living_alone(program: WelfareProgram, profile: BeneficiaryProfile) -> MatchCondition:
    if program.eligibility.living_alone is not True:
        return _condition("livingAlone", "독거 여부", ConditionStatus.NOT_APPLICABLE, "독거 필수 아님")
    if profile.living_alone is None:
        return _condition("livingAlone", "독거 여부", ConditionStatus.UNKNOWN, "독거 여부 확인 필요", True)
    if profile.living_alone:
        return _condition("livingAlone", "독거 여부", ConditionStatus.MATCHED, "독거 조건 충족", True)
    return _condition("livingAlone", "독거 여부", ConditionStatus.NOT_MATCHED, "독거 필수 사업", True)


def derive_income_types(profile: BeneficiaryProfile) -> set[str]:
    values = set(profile.income_types)
    if profile.basic_livelihood_recipient is True:
        values.add("BASIC_LIVELIHOOD_ANY")
    if profile.medical_aid_recipient is True:
        values.update({"MEDICAL_AID_RECIPIENT", "BASIC_LIVELIHOOD_MEDICAL"})
    if profile.near_poverty_status is True:
        values.add("NEAR_POVERTY")
    if profile.basic_pension_recipient is True:
        values.add("BASIC_PENSION_RECIPIENT")
    if profile.registered_disabled is True:
        values.add("REGISTERED_DISABLED")
    return values


def income_code_matches(required: str, known: set[str]) -> bool:
    if required == "ANY" or required in known:
        return True
    if required.startswith("BASIC_LIVELIHOOD_") and "BASIC_LIVELIHOOD_ANY" in known:
        return True
    if required == "BASIC_LIVELIHOOD_ANY" and any(item.startswith("BASIC_LIVELIHOOD_") for item in known):
        return True
    if required.startswith("NEAR_POVERTY") and "NEAR_POVERTY" in known:
        return True
    return False


def evaluate_income(program: WelfareProgram, profile: BeneficiaryProfile) -> MatchCondition:
    required = program.eligibility.income_types
    if not required or "ANY" in required:
        return _condition("income", "소득·자격", ConditionStatus.NOT_APPLICABLE, "소득 제한 없음 또는 다른 자격과 병행 가능")
    known = derive_income_types(profile)
    joined = ", ".join(required)
    if not known:
        return _condition("income", "소득·자격", ConditionStatus.UNKNOWN, f"다음 중 해당 여부 확인: {joined}", True)
    if any(income_code_matches(item, known) for item in required):
        return _condition("income", "소득·자격", ConditionStatus.MATCHED, "입력한 수급·소득자격과 후보 조건이 일치", True)
    if profile.income_information_complete:
        return _condition("income", "소득·자격", ConditionStatus.NOT_MATCHED, f"필요 자격과 불일치: {joined}", True)
    return _condition("income", "소득·자격", ConditionStatus.UNKNOWN, f"현재 입력으로 확인 불가: {joined}", True)


def score_relevance(program: WelfareProgram, profile: BeneficiaryProfile) -> tuple[int, list[str], list[str]]:
    program_categories = {program.category, *program.related_categories}
    matched_needs = [need for need in dict.fromkeys(profile.needs) if need in program_categories]
    tags = set(profile.tags)
    matched_tags = [tag for tag in program.match_tags if tag in tags]

    score = len(matched_needs) * SCORE_PER_MATCHED_NEED + len(matched_tags) * SCORE_PER_MATCHED_TAG
    if any(item in program.eligibility.assistance_need for item in profile.assistance_need):
        score += SCORE_ASSISTANCE_MATCH
    return score, matched_needs, matched_tags


def evaluate_program(program: WelfareProgram, profile: BeneficiaryProfile | None = None) -> ProgramMatch:
    """프로필 하나에 대해 사업 하나의 추천상태·점수·판정근거를 계산한다."""
    profile = profile or BeneficiaryProfile()
    conditions = [
        evaluate_age(program, profile),
        evaluate_region(program, profile),
        evaluate_living_alone(program, profile),
        evaluate_income(program, profile),
    ]
    score, matched_needs, matched_tags = score_relevance(program, profile)

    for item in conditions:
        if item.status is ConditionStatus.MATCHED:
            score += SCORE_CONDITION_MATCHED
        elif item.status is ConditionStatus.UNKNOWN:
            score += SCORE_CONDITION_UNKNOWN
        elif item.status is ConditionStatus.NOT_MATCHED:
            score += SCORE_CONDITION_NOT_MATCHED
    score = max(0, min(100, score))

    hard_mismatch = any(item.hard and item.status is ConditionStatus.NOT_MATCHED for item in conditions)
    hard_unknown = any(item.hard and item.status is ConditionStatus.UNKNOWN for item in conditions)
    if hard_mismatch:
        status = MatchStatus.NOT_ELIGIBLE
    elif hard_unknown:
        status = MatchStatus.NEEDS_CONFIRMATION
    else:
        status = MatchStatus.LIKELY

    return ProgramMatch(
        program=program,
        status=status,
        score=score,
        conditions=conditions,
        matched_needs=matched_needs,
        matched_tags=matched_tags,
        confirmation_items=program.eligibility.conditions,
    )


def find_program_matches(
    programs: Iterable[WelfareProgram],
    profile: BeneficiaryProfile | None = None,
    *,
    filters: SearchFilters | None = None,
    include_not_eligible: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> list[ProgramMatch]:
    """검색 조건을 먼저 적용한 뒤 추천상태 → 점수 → 사업명 순으로 정렬한다."""
    filtered = search_programs(programs, filters)
    results = [evaluate_program(program, profile) for program in filtered]
    if not include_not_eligible:
        results = [result for result in results if result.status is not MatchStatus.NOT_ELIGIBLE]
    results.sort(key=lambda result: (STATUS_RANK[result.status], -result.score, result.program.name))

    offset = max(0, offset)
    if limit is None:
        return results[offset:]
    return results[offset : offset + max(0, limit)]
