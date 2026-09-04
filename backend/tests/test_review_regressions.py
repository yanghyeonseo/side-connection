"""코드리뷰에서 나온 결함들의 회귀 테스트."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.services import ai, opendata
from app.services.cases import merge_helper_answers
from app.services.profile import answers_to_profile


def test_helper_option_answers_reach_matching_profile():
    """보호자 선택지는 원래 질문 문구 그대로여야 매칭 엔진이 해석한다."""
    merged = merge_helper_answers({"receiving": "기초연금,생계비 지원", "need": "식사·혼자 생활"})
    profile = answers_to_profile(merged)
    assert profile.basic_pension_recipient is True
    assert profile.basic_livelihood_recipient is True
    assert "MEAL" in profile.needs and "CARE" in profile.needs


def test_helper_cannot_overwrite_existing_answers(client):
    session = client.post("/api/v1/sessions", json={"mode": "self"}).json()
    sid, code = session["sessionId"], session["caseCode"]
    client.put(f"/api/v1/sessions/{sid}/answers/household", json={"value": "배우자와 살아요"})

    response = client.put(
        f"/api/v1/helper/cases/{code}/answers", json={"answers": {"household": "혼자 살아요"}}
    )
    assert response.status_code == 400, "이미 답한 항목은 보호자가 덮어쓸 수 없다"
    assert client.get(f"/api/v1/sessions/{sid}").json()["answers"]["household"] == "배우자와 살아요"


def test_case_lookup_rate_limit(settings):
    limited = settings.model_copy(update={"case_lookup_limit": 3})
    with TestClient(create_app(limited)) as client:
        statuses = [client.get("/api/v1/admin/cases/00000000").status_code for _ in range(5)]
    assert statuses[:3] == [404, 404, 404]
    assert statuses[3] == 429, "제한 초과 후에는 429를 돌려준다"


def test_admin_case_response_is_not_cacheable(client):
    session = client.post("/api/v1/sessions", json={"mode": "self"}).json()
    response = client.get(f"/api/v1/admin/cases/{session['caseCode']}")
    assert response.headers["Cache-Control"] == "no-store"


def test_opendata_accepts_string_ages():
    condition = {"JA0110": "065", "JA0111": "120"}
    service = {"서비스명": "테스트", "서비스목적요약": "요약", "지원대상": "", "서비스분야": ""}
    assert opendata._is_elderly_relevant(service, condition) is True
    assert opendata._as_int("065") == 65
    assert opendata._as_int(None) is None
    assert opendata._as_int("상시") is None


def test_ai_prompt_excludes_detailed_address():
    formatted = ai._format_answers(
        {"area": "서울특별시 종로구", "areaDetail": "행복아파트 101동 502호", "housingDetail": "보증금 500"}
    )
    assert "행복아파트" not in formatted and "보증금" not in formatted
    assert "서울특별시" in formatted and "종로구" not in formatted, "지역은 시·도 수준까지만 보낸다"


def test_curate_matches_applies_ai_output(client, settings, monkeypatch):
    from app.schemas.matching import Benefit, MatchingResponse, MatchStatus

    result = MatchingResponse(
        benefits=[
            Benefit(
                id="p1", name="사업", tag="확인이 필요해요", summary="s", amount="a", reason="원래 문구",
                location="l", supplies=[], eligibility_status=MatchStatus.NEEDS_CONFIRMATION,
            )
        ],
        needs_guardian_input=[],
    )
    monkeypatch.setattr(ai, "_chat", lambda *args, **kwargs: '{"summary": "요약", "reasons": {"p1": "쉬운 문구"}}')
    curated = ai.curate_matches(settings, {}, result)
    assert curated.ai_summary == "요약"
    assert curated.benefits[0].reason == "쉬운 문구"


def test_answer_size_limits(client):
    session = client.post("/api/v1/sessions", json={"mode": "self"}).json()
    sid = session["sessionId"]
    response = client.put(f"/api/v1/sessions/{sid}/answers/areaDetail", json={"value": "가" * 501})
    assert response.status_code == 422, "500자 초과 답변은 거절한다"
