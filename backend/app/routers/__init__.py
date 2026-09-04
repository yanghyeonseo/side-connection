from fastapi import APIRouter

from . import departments, health, matches, programs, questions, sessions

api_router = APIRouter()
api_router.include_router(departments.router)
api_router.include_router(programs.router)
api_router.include_router(matches.router)
api_router.include_router(questions.router)
api_router.include_router(sessions.router)

__all__ = ["api_router", "health"]
