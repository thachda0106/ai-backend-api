"""Search API router."""

from fastapi import APIRouter, Depends, status

from app.api.dependencies.container import SearchUseCaseDep
from app.api.schemas.common import ErrorResponse
from app.api.schemas.search import SearchRequest as ApiSearchRequest
from app.api.schemas.search import SearchResponse as ApiSearchResponse
from app.api.schemas.search import SearchResultResponse
from app.application.dto.search import SearchRequest as DtoSearchRequest
from app.core.security.api_key import RequireAPIKey

router = APIRouter(
    prefix="/search",
    tags=["Search"],
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
    response_model=ApiSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic document search",
    description="Perform a semantic search across ingested documents using natural language.",
)
async def search_documents(
    request: ApiSearchRequest,
    use_case: SearchUseCaseDep,
) -> ApiSearchResponse:
    """Handle semantic search request."""
    # Map API schema to Application DTO
    dto_request = DtoSearchRequest(
        query=request.query,
        collection_id=request.collection_id,
        top_k=request.top_k,
        filters=request.filters,
    )

    # Execute use case
    dto_response = await use_case.execute(dto_request)

    # Map Application DTO results to API schema results
    api_results = [
        SearchResultResponse(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            content=r.content,
            score=r.score,
            metadata=r.metadata,
            document_title=r.document_title,
            chunk_index=r.chunk_index,
        )
        for r in dto_response.results
    ]

    # Return final API response
    return ApiSearchResponse(
        results=api_results,
        total=dto_response.total,
        query_tokens=dto_response.query_tokens,
    )
