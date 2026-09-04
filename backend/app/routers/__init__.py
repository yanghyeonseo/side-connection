from fastapi import APIRouter

from . import cases, departments, health, matches, programs, questions, sessions

api_router = APIRouter()
api_router.include_router(departments.router)
api_router.include_router(programs.router)
api_router.include_router(matches.router)
api_router.include_router(questions.router)
api_router.include_router(sessions.router)
api_router.include_router(cases.router)

__all__ = ["api_router", "health"]
