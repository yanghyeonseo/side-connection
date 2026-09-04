from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    """외부 서비스(OpenAI·공공데이터포털) 없이 정적 데이터만으로 도는 테스트 설정."""
    return Settings(
        openai_key=None,
        gov24_service_key=None,
        welfare_info_service_key=None,
        open_data_cache_dir=tmp_path / "cache",
        data_dir=REPO_ROOT / "data",
        frontend_dist_dir=tmp_path / "no-dist",
    )


@pytest.fixture()
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
