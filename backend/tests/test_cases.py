"""사례번호 기반 행정 확인·보호자 보완 흐름을 검증한다."""


def _session(client):
    return client.post("/api/v1/sessions", json={"mode": "self"}).json()


def test_admin_case_shows_statement_summary(client):
    session = _session(client)
    sid, code = session["sessionId"], session["caseCode"]
    for question_id, value in [
        ("area", "서울특별시 종로구"),
        ("household", "혼자 살아요"),
        ("income", "30만 원 아래"),
        ("receiving", ["기초연금"]),
    ]:
        client.put(f"/api/v1/sessions/{sid}/answers/{question_id}", json={"value": value})

    response = client.get(f"/api/v1/admin/cases/{code}")
    assert response.status_code == 200
    body = response.json()
    assert body["caseCode"] == code
    assert "서울특별시 종로구" in body["address"]
    assert "30만 원 아래" in body["incomeBand"]
    assert body["recommendedBenefits"]
    assert "확인" in body["note"]


def test_admin_case_unknown_code_is_404(client):
    assert client.get("/api/v1/admin/cases/00000000").status_code == 404


def test_helper_case_lists_only_missing_fields(client):
    session = _session(client)
    sid, code = session["sessionId"], session["caseCode"]
    client.put(f"/api/v1/sessions/{sid}/answers/household", json={"value": "혼자 살아요"})
    client.put(f"/api/v1/sessions/{sid}/answers/income", json={"value": "잘 모르겠어요"})

    fields = {field["id"]: field for field in client.get(f"/api/v1/helper/cases/{code}").json()["missingFields"]}
    assert "income" in fields, "'잘 모르겠어요'는 보완 대상"
    assert "household" not in fields, "이미 답한 항목은 보완 대상이 아니다"
    assert fields["income"]["options"], "보호자용 선택지가 있어야 한다"


def test_helper_answers_merge_into_session(client):
    session = _session(client)
    sid, code = session["sessionId"], session["caseCode"]
    response = client.put(
        f"/api/v1/helper/cases/{code}/answers",
        json={"answers": {"income": "30만 원 아래", "receiving": "기초연금, 생계비 지원", "bogus": "버려짐"}},
    )
    assert response.status_code == 204

    answers = client.get(f"/api/v1/sessions/{sid}").json()["answers"]
    assert answers["income"] == "30만 원 아래"
    assert answers["receiving"] == ["기초연금", "생계비 지원"], "복수 선택 질문은 목록으로 저장"
    assert "bogus" not in answers


def test_housing_detail_requested_when_renting(client):
    session = _session(client)
    sid, code = session["sessionId"], session["caseCode"]
    client.put(f"/api/v1/sessions/{sid}/answers/housing", json={"value": "전세·월세예요"})
    field_ids = [field["id"] for field in client.get(f"/api/v1/helper/cases/{code}").json()["missingFields"]]
    assert "housingDetail" in field_ids
