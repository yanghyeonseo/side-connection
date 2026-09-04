"""공공데이터포털 실시간 수집.

두 데이터셋을 내려받아 정적 큐레이션 데이터(`data/departments/*.json`)와 합친다.

- [행정안전부] 대한민국 공공서비스(혜택) 정보: 정부24 전체 서비스 약 1만 건 중
  어르신 관련 사업만 골라낸다 (연령 조건 + 키워드).
- [한국사회보장정보원] 복지서비스정보: 복지로 중앙부처 복지서비스 스냅숏.

원칙
- 원문이 확정해 주지 않는 자격(소득·지역 세부)은 비워 두어 매칭 엔진이
  '확인 필요'로 판정하게 한다. 수집 데이터가 자격을 단정하지 않는다.
- 네트워크 실패 시 디스크 캐시, 캐시도 없으면 정적 데이터만으로 동작한다.
"""

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from app.config import Settings
from app.schemas.catalog import Department
from app.schemas.program import WelfareProgram
from app.services.catalog import WelfareCatalog
from app.services.search import normalize_text

logger = logging.getLogger(__name__)

ODCLOUD_BASE = "https://api.odcloud.kr/api"
GOV24_SERVICE_LIST = "/gov24/v3/serviceList"
GOV24_SUPPORT_CONDITIONS = "/gov24/v3/supportConditions"
GOV24_SERVICE_DETAIL = "/gov24/v3/serviceDetail"
BOKJIRO_SERVICES = "/15083323/v1/uddi:3929b807-3420-44d7-a851-cc741fce65a1"

PAGE_SIZE = 1000
REQUEST_TIMEOUT = 60.0
CACHE_FILE = "open-data.json"

GOV24_DEPARTMENT = Department(id="gov24-open-data", name="정부24 공공서비스(혜택)", scope="전국·지자체", program_count=0)
BOKJIRO_DEPARTMENT = Department(id="bokjiro-open-data", name="복지로 중앙부처 복지서비스", scope="전국", program_count=0)

ELDERLY_KEYWORDS = re.compile(r"노인|어르신|고령|노년|독거|치매|장기요양|기초연금|경로|요양보호")
ELDERLY_MIN_AGE = 60
ELDERLY_AGE = 65

# 정부24 서비스분야 → 서비스 카테고리 기본값. 키워드로 한 번 더 다듬는다.
FIELD_CATEGORIES = {
    "보건·의료": "MEDICAL",
    "생활안정": "LIVING",
    "보호·돌봄": "CARE",
    "주거·자립": "HOUSING",
    "행정·안전": "SAFETY",
}
KEYWORD_CATEGORIES = [
    (re.compile(r"급식|식사|도시락|밑반찬|경로식당"), "MEAL"),
    (re.compile(r"교통|이동지원|택시|버스요금"), "MOBILITY"),
    (re.compile(r"주택|주거|임대|월세|전세"), "HOUSING"),
    (re.compile(r"응급|안전확인|안심서비스"), "SAFETY"),
    (re.compile(r"의료비|진료|검진|치료|수술"), "MEDICAL"),
    (re.compile(r"돌봄|요양|간병"), "CARE"),
]
KEYWORD_MATCH_TAGS = [
    (re.compile(r"독거"), "LIVING_ALONE"),
    (re.compile(r"급식|식사|도시락|밑반찬"), "MEAL_PREP_DIFFICULTY"),
    (re.compile(r"돌봄|요양|간병"), "DAILY_LIVING_DIFFICULTY"),
    (re.compile(r"의료비|진료비|병원비"), "MEDICAL_EXPENSE_BURDEN"),
    (re.compile(r"교통|이동지원"), "MOBILITY_DIFFICULTY"),
    (re.compile(r"응급|안전확인|안심"), "EMERGENCY_SAFETY_RISK"),
    (re.compile(r"월세|임대료"), "RENT_BURDEN"),
]

# 소관기관 유형별 지원 지역 해석. 기관명이 지역명이 아닌 유형은 판단 불가로 남긴다.
REGIONAL_ORG_TYPES = frozenset({"시군구", "광역시도"})
NATIONWIDE_ORG_TYPES = frozenset({"중앙행정기관", "공공기관"})

LOW_INCOME_CODES = ["BASIC_LIVELIHOOD_ANY", "NEAR_POVERTY"]
FALLBACK_DOCUMENT = "신분증 (자세한 서류는 접수기관 문의)"


def _fetch_all(client: httpx.Client, path: str, service_key: str) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        response = client.get(
            f"{ODCLOUD_BASE}{path}",
            params={"page": page, "perPage": PAGE_SIZE, "serviceKey": service_key},
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data") or []
        rows.extend(data)
        if not data or len(rows) >= int(body.get("totalCount") or 0):
            return rows
        page += 1


def _clean_line(value: object, limit: int) -> str:
    text = re.sub(r"[\s\r\n]+", " ", str(value or "")).strip(" -○·※□■◦*")
    return text[: limit - 1] + "…" if len(text) > limit else text


MEANINGLESS_LINES = frozenset({"해당없음", "없음", "-"})


def _split_lines(value: object, *, max_items: int, limit: int) -> list[str]:
    parts = re.split(r"[\r\n]+|\|\|", str(value or ""))
    items = [
        cleaned
        for part in parts
        if (cleaned := _clean_line(part, limit)) and cleaned not in MEANINGLESS_LINES
    ]
    return items[:max_items]


def _pick_category(field: str, text: str) -> tuple[str, list[str]]:
    """대표 카테고리는 정부 분류(서비스분야)를 우선하고, 키워드는 관련 카테고리로 보탠다."""
    hits = list(dict.fromkeys(category for pattern, category in KEYWORD_CATEGORIES if pattern.search(text)))
    primary = FIELD_CATEGORIES.get(field) or (hits[0] if hits else "LIVING")
    related = [category for category in hits if category != primary]
    return primary, related


def _match_tags(text: str) -> list[str]:
    return [tag for pattern, tag in KEYWORD_MATCH_TAGS if pattern.search(text)]


def _coverage(org_type: str, org_name: str) -> list[str]:
    if org_type in NATIONWIDE_ORG_TYPES:
        return ["전국"]
    if org_type in REGIONAL_ORG_TYPES and org_name:
        return [org_name]
    return ["전국-지자체별상이"]


def _is_elderly_relevant(service: dict, condition: dict) -> bool:
    max_age = condition.get("JA0111")
    if isinstance(max_age, int) and max_age < ELDERLY_AGE:
        return False
    min_age = condition.get("JA0110")
    if isinstance(min_age, int) and min_age >= ELDERLY_MIN_AGE:
        return True
    text = " ".join(str(service.get(key) or "") for key in ("서비스명", "서비스목적요약", "지원대상", "서비스분야"))
    return bool(ELDERLY_KEYWORDS.search(text))


def _income_types(condition: dict) -> list[str]:
    """저소득 구간만 지원하는 신호가 명확할 때만 소득 후보 조건을 단다."""
    low = any(condition.get(code) == "Y" for code in ("JA0201", "JA0202"))
    high = any(condition.get(code) == "Y" for code in ("JA0204", "JA0205"))
    return list(LOW_INCOME_CODES) if low and not high else []


def _basis_year(service: dict) -> int:
    raw = str(service.get("수정일시") or service.get("등록일시") or "")
    return int(raw[:4]) if raw[:4].isdigit() else date.today().year


def _gov24_program(service: dict, condition: dict, detail: dict) -> WelfareProgram | None:
    name = _clean_line(service.get("서비스명"), 80)
    summary = _clean_line(service.get("서비스목적요약"), 200)
    if not name or not summary:
        return None
    text = f"{name} {summary} {service.get('지원대상') or ''} {service.get('지원내용') or ''}"
    category, related = _pick_category(str(service.get("서비스분야") or ""), text)
    deadline_raw = _clean_line(service.get("신청기한"), 120)
    is_always_open = "상시" in deadline_raw or not deadline_raw
    min_age = condition.get("JA0110")
    max_age = condition.get("JA0111")

    conditions = _split_lines(service.get("선정기준"), max_items=1, limit=120)
    conditions.append("정부24 상세 페이지에서 최신 자격·기간 확인")

    return WelfareProgram.model_validate(
        {
            "id": f"gov24-{service.get('서비스ID')}",
            "name": name,
            "summary": summary,
            "managingOrganization": str(service.get("소관기관명") or "정부24"),
            "managingDepartment": str(service.get("부서명") or ""),
            "departmentId": GOV24_DEPARTMENT.id,
            "departmentName": GOV24_DEPARTMENT.name,
            "status": "ACTIVE",
            "coverage": _coverage(str(service.get("소관기관유형") or ""), str(service.get("소관기관명") or "")),
            "category": category,
            "relatedCategories": related,
            "serviceTypes": _split_lines(service.get("지원유형"), max_items=3, limit=40),
            "eligibility": {
                "minAge": min_age if isinstance(min_age, int) else None,
                "maxAge": max_age if isinstance(max_age, int) else None,
                "incomeTypes": _income_types(condition),
                "conditions": conditions,
            },
            "benefits": _split_lines(service.get("지원내용"), max_items=3, limit=120) or [summary],
            "requiredDocuments": _split_lines(detail.get("구비서류"), max_items=5, limit=80) or [FALLBACK_DOCUMENT],
            "application": {
                "periodType": "상시신청" if is_always_open else "기간·공고별",
                "deadline": None if is_always_open else deadline_raw,
                "method": ", ".join(_split_lines(service.get("신청방법"), max_items=3, limit=40)) or "접수기관 문의",
                "organization": _clean_line(service.get("접수기관") or service.get("소관기관명"), 60) or "접수기관 문의",
                "contact": ", ".join(_split_lines(service.get("전화문의"), max_items=2, limit=40)) or None,
            },
            "source": {
                "name": "정부24 공공서비스(혜택)",
                "url": str(service.get("상세조회URL") or "https://www.gov.kr"),
                "basisYear": _basis_year(service),
                "verifiedAt": date.today().isoformat(),
            },
            "matchTags": _match_tags(text),
        }
    )


def _bokjiro_program(row: dict) -> WelfareProgram | None:
    name = _clean_line(row.get("서비스명"), 80)
    summary = _clean_line(row.get("서비스요약"), 200)
    text = f"{name} {summary}"
    if not name or not summary or not ELDERLY_KEYWORDS.search(text):
        return None
    category, related = _pick_category("", text)
    year = row.get("기준연도")
    return WelfareProgram.model_validate(
        {
            "id": f"bokjiro-{row.get('서비스아이디')}",
            "name": name,
            "summary": summary,
            "managingOrganization": str(row.get("소관부처명") or "보건복지부"),
            "managingDepartment": str(row.get("소관조직명") or ""),
            "departmentId": BOKJIRO_DEPARTMENT.id,
            "departmentName": BOKJIRO_DEPARTMENT.name,
            "status": "ACTIVE",
            "coverage": ["전국"],
            "category": category,
            "relatedCategories": related,
            "eligibility": {"conditions": ["복지로 상세 페이지에서 최신 자격 확인"]},
            "benefits": [summary],
            "requiredDocuments": [FALLBACK_DOCUMENT],
            "application": {
                "periodType": "상시신청",
                "method": "복지로 안내 확인",
                "organization": "주민센터 또는 복지로",
                "contact": _clean_line(row.get("대표문의"), 60) or None,
            },
            "source": {
                "name": "복지로 복지서비스정보",
                "url": str(row.get("서비스URL") or "https://www.bokjiro.go.kr"),
                "basisYear": year if isinstance(year, int) else date.today().year,
                "verifiedAt": date.today().isoformat(),
            },
            "matchTags": _match_tags(text),
        }
    )


def fetch_open_programs(settings: Settings) -> list[WelfareProgram]:
    """두 공공 API를 내려받아 어르신 관련 사업만 프로그램 목록으로 만든다."""
    programs: list[WelfareProgram] = []
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        if settings.gov24_service_key:
            services = _fetch_all(client, GOV24_SERVICE_LIST, settings.gov24_service_key)
            conditions = {
                row.get("서비스ID"): row
                for row in _fetch_all(client, GOV24_SUPPORT_CONDITIONS, settings.gov24_service_key)
            }
            details = {
                row.get("서비스ID"): row
                for row in _fetch_all(client, GOV24_SERVICE_DETAIL, settings.gov24_service_key)
            }
            for service in services:
                condition = conditions.get(service.get("서비스ID")) or {}
                if not _is_elderly_relevant(service, condition):
                    continue
                program = _gov24_program(service, condition, details.get(service.get("서비스ID")) or {})
                if program is not None:
                    programs.append(program)
        if settings.welfare_info_service_key:
            for row in _fetch_all(client, BOKJIRO_SERVICES, settings.welfare_info_service_key):
                program = _bokjiro_program(row)
                if program is not None:
                    programs.append(program)
    logger.info("공공데이터 수집 완료: %d개 사업", len(programs))
    return programs


def cache_path(settings: Settings) -> Path:
    return settings.open_data_cache_dir / CACHE_FILE


def save_cache(settings: Settings, programs: list[WelfareProgram]) -> None:
    path = cache_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "programs": [program.model_dump(mode="json", by_alias=True) for program in programs],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def load_cache(settings: Settings) -> tuple[list[WelfareProgram], datetime] | None:
    path = cache_path(settings)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetchedAt"])
        programs = [WelfareProgram.model_validate(raw) for raw in payload["programs"]]
        return programs, fetched_at
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("공공데이터 캐시를 읽지 못해 무시합니다: %s", exc)
        return None


def is_cache_fresh(fetched_at: datetime, settings: Settings) -> bool:
    age = datetime.now(timezone.utc) - fetched_at
    return age.total_seconds() < settings.open_data_refresh_hours * 3600


def _dedupe_key(program: WelfareProgram) -> str:
    """같은 사업 판별 키. 이름이 같아도 소관기관이 다르면(지역별 동명 사업) 다른 사업으로 본다."""
    return f"{normalize_text(program.name)}|{normalize_text(program.managing_organization)}"


def merge_catalog(base: WelfareCatalog, open_programs: list[WelfareProgram]) -> WelfareCatalog:
    """정적 큐레이션 카탈로그에 수집 사업을 합친다. 같은 사업이면 큐레이션이 이긴다.

    전국 사업은 이름만 같아도 중복으로 보고, 지역 사업은 지역별 동명 사업일 수
    있으므로 소관기관까지 같을 때만 중복으로 본다.
    """
    seen = {_dedupe_key(program) for program in base.programs}
    curated_names = {normalize_text(program.name) for program in base.programs}
    merged = list(base.programs)
    counts = {GOV24_DEPARTMENT.id: 0, BOKJIRO_DEPARTMENT.id: 0}
    for program in open_programs:
        key = _dedupe_key(program)
        if key in seen:
            continue
        if program.coverage == ["전국"] and normalize_text(program.name) in curated_names:
            continue
        seen.add(key)
        merged.append(program)
        counts[program.department_id] = counts.get(program.department_id, 0) + 1

    departments = list(base.departments)
    for department in (GOV24_DEPARTMENT, BOKJIRO_DEPARTMENT):
        if counts.get(department.id):
            departments.append(department.model_copy(update={"program_count": counts[department.id]}))
    return WelfareCatalog(base.manifest, departments, merged)
