"""곁이음 백엔드 API 진입점.

프론트엔드(`frontend/src/api/client.ts`)가 브라우저 안에서 수행하던
세션 생성 → 답변 저장 → 사업 매칭 → 안내문 생성 흐름을 HTTP API로 제공한다.
데이터는 저장소의 `data/` 정적 JSON을 기동 시 한 번 읽어 메모리에 올린다.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from threading import Event, Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings
from app.routers import api_router, health
from app.services import opendata
from app.services.catalog import WelfareCatalog, load_catalog
from app.services.ratelimit import RateLimiter
from app.services.sessions import SessionStore

logger = logging.getLogger(__name__)

DESCRIPTION = """
취약계층 공공지원사업 안내 서비스 **곁이음**의 백엔드 API입니다.

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


class SpaStaticFiles(StaticFiles):
    """없는 경로는 index.html로 응답하는 SPA용 정적 서빙. API 경로는 404를 그대로 둔다.

    Starlette 버전에 따라 404가 응답 또는 예외로 오므로 둘 다 처리한다.
    """

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and not path.startswith("api/"):
            return await super().get_response("index.html", scope)
        return response


def _refresh_open_data(app: FastAPI, settings: Settings, base_catalog: WelfareCatalog) -> None:
    """공공데이터를 새로 받아 카탈로그를 교체한다. 실패해도 기존 카탈로그로 계속 동작."""
    try:
        programs = opendata.fetch_open_programs(settings)
        if programs:
            opendata.save_cache(settings, programs)
            app.state.catalog = opendata.merge_catalog(base_catalog, programs)
            logger.info("카탈로그 갱신: 총 %d개 사업", len(app.state.catalog))
    except Exception:
        # 수집은 최선-노력 작업이다. 어떤 실패도 서버를 멈추게 하지 않는다.
        logger.exception("공공데이터 수집 실패, 기존 카탈로그 유지")


def _open_data_refresh_loop(
    app: FastAPI, settings: Settings, base_catalog: WelfareCatalog, stop: Event
) -> None:
    """캐시가 낡았으면 수집하고, 갱신 주기마다 반복한다."""
    interval = settings.open_data_refresh_hours * 3600
    while not stop.is_set():
        cached = opendata.load_cache(settings)
        if cached is None or not opendata.is_cache_fresh(cached[1], settings):
            _refresh_open_data(app, settings, base_catalog)
            wait = interval
        else:
            elapsed = (datetime.now(timezone.utc) - cached[1]).total_seconds()
            wait = max(60.0, interval - elapsed)
        stop.wait(wait)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        base_catalog = load_catalog(settings.data_dir)
        app.state.catalog = base_catalog
        app.state.sessions = SessionStore(
            ttl=timedelta(minutes=settings.session_ttl_minutes),
            max_sessions=settings.max_sessions,
        )
        app.state.case_lookup_limiter = RateLimiter(
            limit=settings.case_lookup_limit,
            window_seconds=settings.case_lookup_window_seconds,
        )

        # 캐시가 있으면 즉시 반영한다. 이후 수집은 설정에 따라
        # 주기 갱신 루프 또는 기동 시 1회(캐시가 낡았을 때만)로 동작한다.
        cached = opendata.load_cache(settings)
        if cached is not None:
            app.state.catalog = opendata.merge_catalog(base_catalog, cached[0])
        stop_refresh = Event()
        if settings.gov24_service_key or settings.welfare_info_service_key:
            cache_stale = cached is None or not opendata.is_cache_fresh(cached[1], settings)
            if settings.open_data_auto_refresh:
                Thread(
                    target=_open_data_refresh_loop,
                    args=(app, settings, base_catalog, stop_refresh),
                    daemon=True,
                ).start()
            elif cache_stale:
                Thread(
                    target=_refresh_open_data, args=(app, settings, base_catalog), daemon=True
                ).start()

        yield
        stop_refresh.set()
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

    # 빌드된 프론트엔드가 있으면 같은 출처에서 함께 서빙한다 (CORS 불필요).
    # /admin/cases/…, /helper/cases/… 같은 SPA 경로는 index.html로 되돌린다.
    if (settings.frontend_dist_dir / "index.html").is_file():
        app.mount("/", SpaStaticFiles(directory=settings.frontend_dist_dir, html=True), name="frontend")
    else:

        @app.get("/", include_in_schema=False)
        def root() -> dict[str, str]:
            return {"name": settings.app_name, "version": settings.version, "docs": "/docs"}

    return app


app = create_app()
