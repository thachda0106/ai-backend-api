"""Document API router."""

from fastapi import APIRouter, Depends, status

from app.api.dependencies.container import IngestUseCaseDep
from app.api.schemas.common import ErrorResponse
from app.api.schemas.document import (
    IngestDocumentRequest as ApiIngestRequest,
)
from app.api.schemas.document import (
    IngestDocumentResponse as ApiIngestResponse,
)
from app.application.dto.document import (
    IngestDocumentRequest as DtoIngestRequest,
)
from app.core.security.api_key import RequireAPIKey

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
    dependencies=[Depends(RequireAPIKey)],
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        429: {"model": ErrorResponse, "description": "Too Many Requests"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
)


@router.post(
    "",
    response_model=ApiIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a document",
    description="Asynchronously ingest a document. The document will be chunked, embedded, and indexed in the background.",
)
async def ingest_document(
    request: ApiIngestRequest,
    use_case: IngestUseCaseDep,
) -> ApiIngestResponse:
    """Handle document ingestion request."""
    # Map API schema to Application DTO
    dto_request = DtoIngestRequest(
        title=request.title,
        content=request.content,
        collection_id=request.collection_id,
        content_type=request.content_type,
        metadata=request.metadata,
    )

    # Execute use case
    dto_response = await use_case.execute(dto_request)

    # Map Application DTO back to API schema
    return ApiIngestResponse(
        document_id=dto_response.document_id,
        job_id=dto_response.job_id,
        status=dto_response.status,
    )
