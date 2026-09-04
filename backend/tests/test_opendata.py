"""공공데이터 매핑·필터·병합 규칙을 네트워크 없이 검증한다."""

from app.services import opendata
from app.services.catalog import load_catalog

GOV24_SERVICE = {
    "서비스ID": "SVC001",
    "서비스명": "독거노인 안부 확인 서비스",
    "서비스목적요약": "홀로 사는 어르신의 안전을 정기적으로 확인합니다.",
    "지원대상": "만 65세 이상 독거노인",
    "지원내용": "○ 주 1회 방문 안부 확인\r\n○ 응급상황 연계",
    "선정기준": "관내 거주 만 65세 이상\r\n기초연금 수급자 우선",
    "신청기한": "상시신청",
    "신청방법": "방문신청||전화신청",
    "전화문의": "종로구청/02-1234-5678",
    "접수기관": "주민센터",
    "소관기관명": "서울특별시 종로구",
    "소관기관유형": "시군구",
    "서비스분야": "보호·돌봄",
    "수정일시": "20260101120000",
    "상세조회URL": "https://www.gov.kr/svc001",
}
CONDITION = {"서비스ID": "SVC001", "JA0110": 65, "JA0111": 120, "JA0201": "Y", "JA0202": "Y"}
DETAIL = {"서비스ID": "SVC001", "구비서류": "신분증\r\n주민등록등본"}


def test_gov24_mapping():
    program = opendata._gov24_program(GOV24_SERVICE, CONDITION, DETAIL)
    assert program is not None
    assert program.id == "gov24-SVC001"
    assert program.category == "CARE"
    assert program.coverage == ["서울특별시 종로구"]
    assert program.eligibility.min_age == 65
    assert program.eligibility.income_types == ["BASIC_LIVELIHOOD_ANY", "NEAR_POVERTY"]
    assert program.required_documents == ["신분증", "주민등록등본"]
    assert program.application.period_type == "상시신청"
    assert "LIVING_ALONE" in program.match_tags


def test_elderly_filter_drops_child_services():
    child = {**GOV24_SERVICE, "서비스명": "유아학비 지원", "서비스목적요약": "유치원 교육비", "지원대상": "3~5세 유아", "서비스분야": "보육·교육"}
    assert opendata._is_elderly_relevant(child, {"JA0110": 3, "JA0111": 5}) is False
    assert opendata._is_elderly_relevant(GOV24_SERVICE, CONDITION) is True
    # 연령 정보가 없어도 키워드로 판단한다
    assert opendata._is_elderly_relevant(GOV24_SERVICE, {}) is True


def test_merge_dedupes_nationwide_by_name_but_keeps_regional(settings):
    base = load_catalog(settings.data_dir)
    curated_name = base.programs[0].name
    nationwide_dup = opendata._gov24_program(
        {**GOV24_SERVICE, "서비스ID": "DUP1", "서비스명": curated_name, "소관기관유형": "중앙행정기관", "소관기관명": "보건복지부"},
        {},
        {},
    )
    regional_same_name = opendata._gov24_program(
        {**GOV24_SERVICE, "서비스ID": "DUP2", "서비스명": curated_name},
        {},
        {},
    )
    merged = opendata.merge_catalog(base, [nationwide_dup, regional_same_name])
    ids = {program.id for program in merged.programs}
    assert "gov24-DUP1" not in ids, "전국 사업은 이름이 같으면 큐레이션이 이긴다"
    assert "gov24-DUP2" in ids, "지역 사업은 지역별 동명 사업으로 유지한다"


def test_cache_roundtrip(settings):
    program = opendata._gov24_program(GOV24_SERVICE, CONDITION, DETAIL)
    opendata.save_cache(settings, [program])
    cached = opendata.load_cache(settings)
    assert cached is not None
    programs, fetched_at = cached
    assert programs[0].id == program.id
    assert opendata.is_cache_fresh(fetched_at, settings) is True
