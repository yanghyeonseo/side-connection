"""검색 조건, 추천 판정 결과, 프론트엔드용 카드 구조."""

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import ConfigDict, Field

from .common import CamelModel
from .profile import BeneficiaryProfile
from .program import WelfareProgram


class MatchStatus(str, Enum):
    LIKELY = "LIKELY"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class ConditionStatus(str, Enum):
    MATCHED = "MATCHED"
    UNKNOWN = "UNKNOWN"
    NOT_MATCHED = "NOT_MATCHED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SearchFilters(CamelModel):
    """조건 종류끼리는 AND, 배열 안은 `arrayMode`(기본 ANY)로 판정한다."""

    keyword: str | None = Field(default=None, description="공백 단위 AND 검색")
    categories: list[str] = Field(default_factory=list)
    related_categories: list[str] = Field(default_factory=list)
    department_ids: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)
    service_types: list[str] = Field(default_factory=list)
    match_tags: list[str] = Field(default_factory=list)
    income_types: list[str] = Field(default_factory=list)
    period_types: list[str] = Field(default_factory=list)
    coverage: list[str] = Field(default_factory=list)
    region: str | None = None
    min_age: int | None = Field(default=None, ge=0)
    max_age: int | None = Field(default=None, ge=0)
    living_alone_only: bool = False
    managing_organization: str | None = None
    only_currently_open: bool = False
    on_date: date | None = Field(default=None, description="접수 여부 판정 기준일. 기본 오늘")
    array_mode: Literal["ANY", "ALL"] = "ANY"


class ProgramListQuery(SearchFilters):
    """`GET /programs` 쿼리 파라미터. 검색 조건에 페이지 크기·오프셋을 더한 것."""

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class MatchCondition(CamelModel):
    key: str
    label: str
    status: ConditionStatus
    detail: str
    hard: bool = Field(default=False, description="true이면 불일치 시 탈락, 미확인 시 확인 필요")


class ProgramMatch(CamelModel):
    program: WelfareProgram
    status: MatchStatus
    score: int = Field(ge=0, le=100)
    conditions: list[MatchCondition]
    matched_needs: list[str]
    matched_tags: list[str]
    confirmation_items: list[str] = Field(description="담당기관에 최종 확인할 원문 세부조건")


class MatchRequest(CamelModel):
    model_config = ConfigDict(
        **CamelModel.model_config,
        json_schema_extra={
            "examples": [
                {
                    "profile": {
                        "age": 78,
                        "region": "서울특별시",
                        "livingAlone": True,
                        "basicPensionRecipient": True,
                        "needs": ["CARE", "MEAL", "MOBILITY"],
                        "assistanceNeed": ["MEDIUM"],
                        "tags": ["LIVING_ALONE", "MEAL_PREP_DIFFICULTY"],
                    },
                    "filters": {"onlyCurrentlyOpen": True},
                    "includeNotEligible": False,
                    "limit": 10,
                }
            ]
        },
    )

    profile: BeneficiaryProfile = Field(default_factory=BeneficiaryProfile)
    filters: SearchFilters = Field(default_factory=lambda: SearchFilters(only_currently_open=True))
    include_not_eligible: bool = False
    limit: int | None = Field(default=None, ge=0, le=100)
    offset: int = Field(default=0, ge=0)


class MatchListResponse(CamelModel):
    total: int
    items: list[ProgramMatch]


class Benefit(CamelModel):
    """프론트엔드 `Benefit` 타입과 1:1로 맞춘 결과 카드."""

    id: str
    name: str
    tag: str
    summary: str
    amount: str
    reason: str
    location: str
    needs_check: str | None = None
    supplies: list[str]
    contact: str | None = None
    source_url: str | None = None
    eligibility_status: MatchStatus


class MatchingResponse(CamelModel):
    """프론트엔드 `MatchingResponse` 타입과 1:1."""

    benefits: list[Benefit]
    needs_guardian_input: list[str] = Field(description="보호자가 보완하면 정확해지는 항목 라벨")
