"""곁에 백엔드 API 진입점.

프론트엔드(`frondend/src/api/client.ts`)가 브라우저 안에서 수행하던
세션 생성 → 답변 저장 → 사업 매칭 → 안내문 생성 흐름을 HTTP API로 제공한다.
데이터는 저장소의 `data/` 정적 JSON을 기동 시 한 번 읽어 메모리에 올린다.
"""

from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.routers import api_router, health
from app.services.catalog import load_catalog
from app.services.sessions import SessionStore

DESCRIPTION = """
취약계층 공공지원사업 안내 서비스 **곁에**의 백엔드 API입니다.

- 로그인·본인인증 없이 세션 코드만으로 동작합니다.
- 답변은 메모리에만 보관되고 TTL이 지나면 삭제됩니다. 주민등록번호·계좌번호는 받지 않습니다.
- 추천 결과는 후보 검색용입니다. 신청 자격의 최종 확정은 담당기관이 합니다.
"""

TAGS = [
    {"name": "health", "description": "서버 상태와 적재된 데이터셋 정보"},
    {"name": "departments", "description": "데이터를 제공하는 담당 영역(부처·기관) 목록"},
    {"name": "programs", "description": "복지사업 목록·검색·상세. `data/` 정적 데이터 기반"},
    {"name": "matches", "description": "프로필 기반 추천 엔진. 세션 없이 직접 호출 가능"},
    {"name": "questions", "description": "상황 입력 질문 흐름"},
    {"name": "sessions", "description": "로그인 없는 세션: 답변 저장, 맞춤 추천, 주민센터 안내문"},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.catalog = load_catalog(settings.data_dir)
        app.state.sessions = SessionStore(ttl=timedelta(minutes=settings.session_ttl_minutes))
        yield
        app.state.sessions.clear()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "version": settings.version, "docs": "/docs"}

    return app


app = create_app()
