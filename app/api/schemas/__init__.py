"""API schemas package — re-exports all request/response models."""

from app.api.schemas.chat import ChatRequest, ChatResponse, SourceResponse, StreamEvent
from app.api.schemas.common import ErrorResponse
from app.api.schemas.document import IngestDocumentRequest, IngestDocumentResponse
from app.api.schemas.search import SearchRequest, SearchResponse, SearchResultResponse

__all__ = [
    # Common
    "ErrorResponse",
    # Document
    "IngestDocumentRequest",
    "IngestDocumentResponse",
    # Search
    "SearchRequest",
    "SearchResponse",
    "SearchResultResponse",
    # Chat
    "ChatRequest",
    "ChatResponse",
    "SourceResponse",
    "StreamEvent",
]
