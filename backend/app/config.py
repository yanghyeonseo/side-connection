"""환경변수 기반 설정.

`GYEOTE_` 접두사를 붙인 환경변수나 `.env` 파일로 덮어쓸 수 있다.
예) GYEOTE_SESSION_TTL_MINUTES=60

외부 서비스 키(OPENAI_KEY, GOV24_SERVICE_KEY 등)는 저장소 루트 `.env`에
접두사 없이 두고 validation_alias로 읽는다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GYEOTE_",
        env_file=(REPO_ROOT / ".env", ".env"),
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

    openai_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_KEY",
        description="OpenAI API 키. 없으면 AI 큐레이션 없이 규칙 기반 문구로 동작",
    )
    openai_model: str = Field(
        default="gpt-5-mini",
        validation_alias="OPENAI_MODEL",
        description="추천 큐레이션·상담원 안내문 생성에 쓸 모델",
    )
    openai_timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        description="AI 호출 제한 시간. 초과하면 규칙 기반 문구로 대체",
    )

    gov24_service_key: str | None = Field(
        default=None,
        validation_alias="GOV24_SERVICE_KEY",
        description="[행정안전부] 대한민국 공공서비스(혜택) 정보 인증키",
    )
    welfare_info_service_key: str | None = Field(
        default=None,
        validation_alias="WELFARE_INFO_SERVICE_KEY",
        description="[한국사회보장정보원] 복지서비스정보 인증키",
    )
    open_data_cache_dir: Path = Field(
        default=REPO_ROOT / "data" / "cache",
        description="공공데이터 수집 결과를 저장할 디렉터리 (gitignore 대상)",
    )
    open_data_refresh_hours: int = Field(
        default=24,
        ge=1,
        description="캐시가 이보다 오래되면 백그라운드에서 다시 수집",
    )

    welfare_center_phone: str = Field(
        default="129",
        validation_alias="WELFARE_CENTER_PHONE",
        description="전화 상담 번호. 기본 129(보건복지상담센터)",
    )
    welfare_center_sms: str | None = Field(
        default=None,
        validation_alias="WELFARE_CENTER_SMS_NUMBER",
        description="문자 수신 번호. 없으면 문자 안내 생략",
    )

    max_sessions: int = Field(
        default=20_000,
        ge=1,
        description="메모리 세션 상한. 넘으면 새 세션 생성을 잠시 거절한다",
    )
    case_lookup_limit: int = Field(
        default=30,
        ge=1,
        description="IP당 사례번호 조회 허용 횟수 (case_lookup_window_seconds 동안)",
    )
    case_lookup_window_seconds: float = Field(
        default=300.0,
        gt=0,
        description="사례번호 조회 제한 윈도. 8자리 코드 무차별 대입 방지",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
