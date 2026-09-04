from fastapi import APIRouter

from app.dependencies import CatalogDep
from app.schemas.catalog import Department

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[Department], summary="담당 영역 목록")
def list_departments(catalog: CatalogDep) -> list[Department]:
    return catalog.departments
