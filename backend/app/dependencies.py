"""라우터에서 공통으로 쓰는 FastAPI 의존성."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.services.catalog import WelfareCatalog
from app.services.sessions import Session, SessionStore


def get_catalog(request: Request) -> WelfareCatalog:
    return request.app.state.catalog


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.sessions


SettingsDep = Annotated[Settings, Depends(get_settings)]
CatalogDep = Annotated[WelfareCatalog, Depends(get_catalog)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]


def get_session(session_id: str, store: SessionStoreDep) -> Session:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="세션을 찾을 수 없거나 만료되었습니다.",
        )
    return session


SessionDep = Annotated[Session, Depends(get_session)]
