from fastapi import APIRouter

from app.dependencies import CatalogDep
from app.schemas.matching import MatchListResponse, MatchRequest
from app.services.matching import find_program_matches

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchListResponse, summary="프로필 기반 추천 (엔진 직접 호출)")
def match_programs(body: MatchRequest, catalog: CatalogDep) -> MatchListResponse:
    """검색 조건을 먼저 적용한 뒤 `LIKELY` → `NEEDS_CONFIRMATION` → 점수 순으로 정렬한다.

    각 결과에는 연령·지역·독거·소득자격 조건별 판정과 근거 문장이 들어 있어
    복지사·보호자 화면에서 판단 근거를 열람할 수 있다.
    """
    all_results = find_program_matches(
        catalog.programs,
        body.profile,
        filters=body.filters,
        include_not_eligible=body.include_not_eligible,
    )
    end = None if body.limit is None else body.offset + body.limit
    return MatchListResponse(total=len(all_results), items=all_results[body.offset : end])
