"""다중 조건 정적 검색. `frondend/welfare-search.js`의 `searchPrograms` 포팅."""

import unicodedata
from collections.abc import Iterable
from datetime import date

from app.schemas.catalog import FilterOptions
from app.schemas.matching import SearchFilters
from app.schemas.program import WelfareProgram

NATIONWIDE = frozenset({"전국"})
UNCERTAIN_NATIONWIDE = frozenset({"전국-지자체별상이", "전국-공고별상이"})


def normalize_text(value: object) -> str:
    """NFKC 정규화 후 소문자화하고 공백·문장부호·기호를 모두 제거한다."""
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return "".join(
        ch for ch in text if not (ch.isspace() or unicodedata.category(ch)[0] in "PS")
    )


def _clean(values: Iterable[object] | None) -> list[object]:
    return [item for item in (values or []) if item not in (None, "")]


def includes_by_mode(values: Iterable[object] | None, selected: Iterable[object] | None, mode: str = "ANY") -> bool:
    wanted = _clean(selected)
    if not wanted:
        return True
    source = set(_clean(values))
    if mode == "ALL":
        return all(item in source for item in wanted)
    return any(item in source for item in wanted)


def text_contains_all(haystack: object, keywords: Iterable[str]) -> bool:
    text = normalize_text(haystack)
    return all(normalize_text(keyword) in text for keyword in keywords)


def search_text(program: WelfareProgram) -> str:
    return " ".join(
        [
            program.name,
            program.summary,
            program.managing_organization,
            program.managing_department,
            *program.coverage,
            program.category,
            *program.related_categories,
            *program.service_types,
            *program.eligibility.conditions,
            *program.benefits,
            *program.match_tags,
        ]
    )


def regions_compatible(coverage: list[str], region: str | None) -> bool | None:
    """True=일치, False=명확히 불일치, None=지자체·공고별로 달라 판단 불가."""
    wanted = normalize_text(region)
    if not wanted:
        return None
    if any(item in NATIONWIDE for item in coverage):
        return True
    if any(item in UNCERTAIN_NATIONWIDE for item in coverage):
        return None
    normalized = [normalize_text(item) for item in coverage]
    return any(item == wanted or item.startswith(wanted) or wanted.startswith(item) for item in normalized)


def age_ranges_overlap(program: WelfareProgram, min_age: int | None, max_age: int | None) -> bool:
    if min_age is None and max_age is None:
        return True
    program_min = program.eligibility.min_age if program.eligibility.min_age is not None else float("-inf")
    program_max = program.eligibility.max_age if program.eligibility.max_age is not None else float("inf")
    query_min = min_age if min_age is not None else float("-inf")
    query_max = max_age if max_age is not None else float("inf")
    return program_min <= query_max and query_min <= program_max


def parse_date(value: object) -> date | None:
    """ISO 날짜만 날짜로 취급한다. '퇴원일로부터 180일 이내' 같은 원문 설명은 None."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def is_application_open(program: WelfareProgram, on_date: date | None = None) -> bool:
    if program.status == "CLOSED":
        return False
    deadline = parse_date(program.application.deadline)
    target = on_date or date.today()
    if deadline and deadline < target:
        return False
    return program.status == "ACTIVE"


def search_programs(programs: Iterable[WelfareProgram], filters: SearchFilters | None = None) -> list[WelfareProgram]:
    filters = filters or SearchFilters()
    mode = filters.array_mode
    keywords = (filters.keyword or "").split()
    on_date = filters.on_date or date.today()

    results: list[WelfareProgram] = []
    for program in programs:
        all_categories = [program.category, *program.related_categories]
        all_income_types = program.eligibility.income_types

        if keywords and not text_contains_all(search_text(program), keywords):
            continue
        if not includes_by_mode(all_categories, filters.categories, mode):
            continue
        if not includes_by_mode(program.related_categories, filters.related_categories, mode):
            continue
        if not includes_by_mode([program.department_id], filters.department_ids, mode):
            continue
        if not includes_by_mode([program.status], filters.statuses, mode):
            continue
        if not includes_by_mode(program.service_types, filters.service_types, mode):
            continue
        if not includes_by_mode(program.match_tags, filters.match_tags, mode):
            continue
        if not includes_by_mode(all_income_types, filters.income_types, mode):
            continue
        if not includes_by_mode([program.application.period_type], filters.period_types, mode):
            continue
        if not includes_by_mode(program.coverage, filters.coverage, mode):
            continue
        if not age_ranges_overlap(program, filters.min_age, filters.max_age):
            continue
        if filters.region and regions_compatible(program.coverage, filters.region) is False:
            continue
        if filters.living_alone_only and program.eligibility.living_alone is not True:
            continue
        if filters.managing_organization and not text_contains_all(
            program.managing_organization, [filters.managing_organization]
        ):
            continue
        if filters.only_currently_open and not is_application_open(program, on_date):
            continue
        results.append(program)
    return results


def get_filter_options(programs: Iterable[WelfareProgram]) -> FilterOptions:
    programs = list(programs)

    def unique(items: Iterable[object]) -> list[str]:
        return sorted({str(item) for item in items if item})

    return FilterOptions(
        categories=unique(item for p in programs for item in [p.category, *p.related_categories]),
        departments=unique(p.department_id for p in programs),
        organizations=unique(p.managing_organization for p in programs),
        coverage=unique(item for p in programs for item in p.coverage),
        service_types=unique(item for p in programs for item in p.service_types),
        income_types=unique(item for p in programs for item in p.eligibility.income_types),
        period_types=unique(p.application.period_type for p in programs),
        match_tags=unique(item for p in programs for item in p.match_tags),
    )
