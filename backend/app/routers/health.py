from fastapi import APIRouter

from app.dependencies import CatalogDep, SessionStoreDep, SettingsDep
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="서버 상태와 데이터셋 정보")
def health(catalog: CatalogDep, store: SessionStoreDep, settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.version,
        dataset=catalog.manifest.dataset,
        program_count=len(catalog.programs),
        department_count=len(catalog.departments),
        active_sessions=len(store),
    )
