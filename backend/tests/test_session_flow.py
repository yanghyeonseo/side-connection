"""문진 → 추천 → 안내문까지 사용자 흐름 전체를 검증한다."""

FULL_ANSWERS = [
    ("birthYear", "1945"),
    ("area", "서울특별시 종로구"),
    ("household", "혼자 살아요"),
    ("children", "있는데 아예 끊겼어요"),
    ("lastContact", "3년 넘게"),
    ("receiving", ["기초연금"]),
    ("need", ["생활비가 부담돼요", "식사·혼자 생활"]),
    ("income", "30만 원 아래"),
    ("housing", "전세·월세예요"),
    ("mobility", "못 해요"),
    ("idCard", "둘 다 있어요"),
    ("visit", "누가 같이 가주면요"),
]


def create_session(client, mode="self"):
    response = client.post("/api/v1/sessions", json={"mode": mode})
    assert response.status_code == 201
    return response.json()


def test_create_session_returns_case_code(client):
    session = create_session(client)
    assert session["sessionId"]
    assert len(session["caseCode"]) == 8
    assert session["caseCode"].isdigit()


def test_full_flow_returns_matches_and_brief(client):
    session = create_session(client)
    sid = session["sessionId"]
    for question_id, value in FULL_ANSWERS:
        response = client.put(f"/api/v1/sessions/{sid}/answers/{question_id}", json={"value": value})
        assert response.status_code == 200, question_id

    response = client.post(f"/api/v1/sessions/{sid}/matches")
    assert response.status_code == 200
    body = response.json()
    assert body["benefits"], "추천 결과가 비면 안 된다"
    assert body["broadened"] is False
    first = body["benefits"][0]
    assert first["tag"] in ("신청해볼 수 있어요", "확인이 필요해요")
    assert first["reason"]

    response = client.get(f"/api/v1/sessions/{sid}/brief")
    assert response.status_code == 200
    assert "곁이음" in response.json()["text"]


def test_unknown_answers_still_produce_results(client):
    """모든 답을 '잘 모르겠어요'로 넘겨도 넓혀 찾은 후보를 준다."""
    session = create_session(client)
    sid = session["sessionId"]
    response = client.post(
        f"/api/v1/sessions/{sid}/matches",
        json={"answers": {question_id: "잘 모르겠어요" for question_id, _ in FULL_ANSWERS}},
    )
    assert response.status_code == 200
    assert response.json()["benefits"], "빈 결과 대신 일반 후보를 제시해야 한다"


def test_extra_answer_ids_accepted(client):
    session = create_session(client)
    sid = session["sessionId"]
    assert client.put(f"/api/v1/sessions/{sid}/answers/areaDetail", json={"value": "○○아파트"}).status_code == 200
    assert client.put(f"/api/v1/sessions/{sid}/answers/nonsense", json={"value": "x"}).status_code == 404


def test_expired_session_not_found(client):
    response = client.get("/api/v1/sessions/no-such-session")
    assert response.status_code == 404
