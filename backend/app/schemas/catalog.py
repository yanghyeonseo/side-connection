"""`data/manifest.json`과 부서 파일 메타데이터."""

from datetime import date

from .common import CamelModel


class DatasetInfo(CamelModel):
    name: str
    as_of: date
    record_count: int | None = None
    department_count: int | None = None
    locale: str = "ko-KR"
    disclaimer: str


class ManifestDepartment(CamelModel):
    id: str
    name: str
    file: str
    program_count: int | None = None


class Manifest(CamelModel):
    schema_version: str
    dataset: DatasetInfo
    departments: list[ManifestDepartment]


class Department(CamelModel):
    id: str
    name: str
    scope: str | None = None
    program_count: int


class FilterOptions(CamelModel):
    """체크박스·셀렉트 UI에 쓸 수 있는, 실제 데이터에 존재하는 값 목록."""

    categories: list[str]
    departments: list[str]
    organizations: list[str]
    coverage: list[str]
    service_types: list[str]
    income_types: list[str]
    period_types: list[str]
    match_tags: list[str]
