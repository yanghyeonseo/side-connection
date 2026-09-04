"""세션 답변 → 추천 카드 한 벌을 만드는 상위 흐름.

정확한 자격을 아직 판단할 수 없다고 해서 결과를 0건으로 끝내지 않는다.
연령·지역·소득은 주민센터에서 최종 확인하도록 남기고, 조건을 넓혀
현재 접수 가능한 일반 후보라도 제시한다(broadened=True).
"""

from app.config import Settings
from app.schemas.matching import MatchingResponse, SearchFilters
from app.schemas.profile import BeneficiaryProfile
from app.schemas.session import AnswerValue
from app.services import ai
from app.services.catalog import WelfareCatalog
from app.services.matching import find_program_matches
from app.services.presenter import build_matching_response
from app.services.profile import answers_to_profile


def _broadened_profile(profile: BeneficiaryProfile) -> BeneficiaryProfile:
    """확정 못 한 조건을 지우고 넓게 다시 찾기 위한 프로필."""
    return profile.model_copy(
        update={"age": None, "region": None, "living_alone": None, "needs": [], "tags": []}
    )


def recommend_for_answers(
    answers: dict[str, AnswerValue],
    catalog: WelfareCatalog,
    settings: Settings,
    *,
    curate: bool = False,
) -> MatchingResponse:
    profile = answers_to_profile(answers)
    filters = SearchFilters(only_currently_open=True)
    matches = find_program_matches(
        catalog.programs, profile, filters=filters, include_not_eligible=False, limit=settings.match_limit
    )
    broadened = False
    if not matches:
        broadened = True
        matches = find_program_matches(
            catalog.programs,
            _broadened_profile(profile),
            filters=filters,
            include_not_eligible=False,
            limit=settings.match_limit,
        )
    result = build_matching_response(matches)
    result.broadened = broadened
    if curate:
        result = ai.curate_matches(settings, answers, result)
    return result
