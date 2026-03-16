"""API routers package."""

from fastapi import APIRouter

from app.api.routers import documents, search

api_router = APIRouter(prefix="/v1")

# Register individual feature routers
api_router.include_router(documents.router)
api_router.include_router(search.router)

__all__ = ["api_router"]
