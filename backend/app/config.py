"""환경변수 기반 설정.

`GYEOTE_` 접두사를 붙인 환경변수나 `.env` 파일로 덮어쓸 수 있다.
예) GYEOTE_SESSION_TTL_MINUTES=60
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GYEOTE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "곁에 API"
    version: str = "0.1.0"

    data_dir: Path = Field(
        default=REPO_ROOT / "data",
        description="manifest.json과 departments/*.json이 있는 디렉터리",
    )
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://yanghyeonseo.github.io",
        ],
        description="브라우저에서 API를 호출할 수 있는 출처",
    )
    session_ttl_minutes: int = Field(
        default=60 * 24,
        ge=1,
        description="세션(답변) 보관 시간. 개인정보 최소 보관 원칙에 따라 만료 후 삭제",
    )
    match_limit: int = Field(
        default=12,
        ge=1,
        le=100,
        description="세션 맞춤 추천에서 반환할 최대 사업 수",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
