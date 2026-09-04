"""`data/departments/*.json`의 사업 레코드 구조. 스키마 버전 2.0.0."""

from datetime import date
from typing import Literal

from pydantic import Field

from .common import CamelModel

Category = Literal["CARE", "LIVING", "MEDICAL", "MEAL", "MOBILITY", "HOUSING", "SAFETY"]
ProgramStatus = Literal["ACTIVE", "CLOSED"]
AssistanceNeed = Literal["LOW", "MEDIUM", "HIGH"]


class Eligibility(CamelModel):
    min_age: int | None = Field(default=None, description="숫자로 단정할 수 있을 때만 존재")
    max_age: int | None = None
    living_alone: bool | None = Field(
        default=None,
        description="true=독거 필수, false=독거 대상 아님, null=필수 아님 또는 가구유형별 상이",
    )
    assistance_need: list[AssistanceNeed] = Field(default_factory=list)
    income_types: list[str] = Field(
        default_factory=list,
        description="정규화된 소득·수급자격 코드. 여러 값은 후보 조건(OR)",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="앱이 자동 확정하면 안 되는 공식 세부 조건과 중복 제한",
    )


class Application(CamelModel):
    period_type: str
    deadline: str | None = Field(default=None, description="ISO 날짜 또는 원문 설명")
    method: str
    organization: str
    contact: str | None = None


class Source(CamelModel):
    name: str
    url: str
    basis_year: int
    verified_at: date | None = None


class WelfareProgram(CamelModel):
    id: str
    name: str
    summary: str
    managing_organization: str
    managing_department: str
    department_id: str
    department_name: str
    status: ProgramStatus
    coverage: list[str] = Field(description="`전국`, `서울특별시`, `전국-지자체별상이` 등")
    category: Category
    related_categories: list[Category] = Field(default_factory=list)
    service_types: list[str] = Field(default_factory=list)
    eligibility: Eligibility
    benefits: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    application: Application
    source: Source
    match_tags: list[str] = Field(default_factory=list)


class ProgramListResponse(CamelModel):
    total: int
    items: list[WelfareProgram]
