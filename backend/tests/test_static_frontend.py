"""백엔드가 빌드된 프론트엔드를 SPA 규칙으로 함께 서빙하는지 검증한다."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_spa_serving_and_fallback(settings, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>곁이음</html>", encoding="utf-8")
    with TestClient(create_app(settings.model_copy(update={"frontend_dist_dir": dist}))) as client:
        assert "곁이음" in client.get("/").text
        assert "곁이음" in client.get("/admin/cases/12345678").text, "SPA 경로는 index.html로 되돌린다"
        assert client.get("/health").json()["status"] == "ok", "API는 그대로 동작한다"
        assert client.get("/api/v1/no-such-endpoint").status_code == 404, "API 404는 HTML로 가리지 않는다"


def test_json_root_without_dist(client):
    body = client.get("/").json()
    assert body["name"] == "곁이음 API"
