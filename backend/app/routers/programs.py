from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CatalogDep
from app.schemas.catalog import FilterOptions
from app.schemas.matching import ProgramListQuery
from app.schemas.program import ProgramListResponse, WelfareProgram
from app.services.search import get_filter_options, search_programs

router = APIRouter(prefix="/programs", tags=["programs"])


@router.get("", response_model=ProgramListResponse, summary="복지사업 검색")
def list_programs(catalog: CatalogDep, query: Annotated[ProgramListQuery, Query()]) -> ProgramListResponse:
    """조건 종류끼리는 AND, 같은 배열 안은 `arrayMode`(기본 ANY)로 검색한다.

    예) `?keyword=병원 동행&categories=CARE&categories=MOBILITY&region=서울특별시&minAge=75`
    """
    results = search_programs(catalog.programs, query)
    return ProgramListResponse(total=len(results), items=results[query.offset : query.offset + query.limit])


@router.get("/filter-options", response_model=FilterOptions, summary="필터 UI 선택지")
def filter_options(catalog: CatalogDep) -> FilterOptions:
    return get_filter_options(catalog.programs)


@router.get("/{program_id}", response_model=WelfareProgram, summary="복지사업 상세")
def read_program(program_id: str, catalog: CatalogDep) -> WelfareProgram:
    program = catalog.get(program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="복지사업을 찾을 수 없습니다.")
    return program
