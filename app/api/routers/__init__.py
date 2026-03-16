"""API routers package."""

from fastapi import APIRouter

from app.api.routers import chat, documents, search

api_router = APIRouter(prefix="/v1")

# Register individual feature routers
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(chat.router)

__all__ = ["api_router"]
