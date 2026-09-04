"""세션 답변 → 추천 카드 한 벌을 만드는 상위 흐름.

정확한 자격을 아직 판단할 수 없다고 해서 결과를 0건으로 끝내지 않는다.
연령·지역·소득은 주민센터에서 최종 확인하도록 남기고, 조건을 넓혀
현재 접수 가능한 일반 후보라도 제시한다(broadened=True).
"""

from collections import OrderedDict
from threading import Lock

from app.config import Settings
from app.schemas.matching import MatchingResponse, SearchFilters
from app.schemas.profile import BeneficiaryProfile
from app.schemas.session import AnswerValue
from app.services import ai
from app.services.catalog import WelfareCatalog
from app.services.matching import find_program_matches
from app.services.presenter import build_matching_response
from app.services.profile import answers_to_profile

# 같은 답변으로 다시 찾을 때 AI 호출을 반복하지 않기 위한 캐시.
_CACHE_LIMIT = 256
_curated_cache: OrderedDict[tuple, MatchingResponse] = OrderedDict()
_cache_lock = Lock()


def answers_cache_key(answers: dict[str, AnswerValue]) -> tuple:
    return tuple(sorted((key, tuple(value) if isinstance(value, list) else value) for key, value in answers.items()))


def _cache_get(key: tuple) -> MatchingResponse | None:
    with _cache_lock:
        cached = _curated_cache.get(key)
        if cached is not None:
            _curated_cache.move_to_end(key)
        return cached.model_copy(deep=True) if cached is not None else None


def _cache_put(key: tuple, result: MatchingResponse) -> None:
    with _cache_lock:
        _curated_cache[key] = result.model_copy(deep=True)
        while len(_curated_cache) > _CACHE_LIMIT:
            _curated_cache.popitem(last=False)


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
    cache_key = ("curated", catalog.version, answers_cache_key(answers)) if curate else None
    if cache_key is not None and (cached := _cache_get(cache_key)) is not None:
        return cached

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
        if cache_key is not None:
            _cache_put(cache_key, result)
    return result
