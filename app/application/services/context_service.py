"""Context window management service.

Manages token budgets for RAG context injection,
ensuring search results fit within the LLM's context window.
"""

from __future__ import annotations

from app.domain.entities.search_result import SearchResult
from app.domain.services.token_service import TokenService


class ContextService:
    """Manages context window token budgets for RAG.

    Takes search results ordered by relevance and fits as many
    as possible within the token budget, formatting them as
    numbered citation blocks.
    """

    def __init__(
        self,
        token_service: TokenService,
        max_context_tokens: int = 3000,
    ) -> None:
        self._token_service = token_service
        self._max_context_tokens = max_context_tokens

    def build_context(
        self,
        search_results: list[SearchResult],
        model: str = "gpt-4o",
    ) -> tuple[str, list[SearchResult]]:
        """Build context string from search results within token budget.

        Iterates results in relevance order, adding content until
        the token budget is exhausted. Never truncates a chunk mid-content.

        Args:
            search_results: List of SearchResult, ordered by score (highest first).
            model: The LLM model name for token counting.

        Returns:
            Tuple of (formatted context string, list of used results).
        """
        if not search_results:
            return "", []

        used_results: list[SearchResult] = []
        blocks: list[str] = []
        current_tokens = 0

        for i, result in enumerate(search_results):
            # Format as a numbered block
            block = self._format_block(i + 1, result)
            block_tokens = self._token_service.count_tokens(block, model)

            # Check if adding this block would exceed budget
            if current_tokens + block_tokens > self._max_context_tokens:
                break

            blocks.append(block)
            used_results.append(result)
            current_tokens += block_tokens

        context = "\n\n".join(blocks)
        return context, used_results

    @staticmethod
    def _format_block(index: int, result: SearchResult) -> str:
        """Format a search result as a numbered citation block.

        Args:
            index: The citation number (1-based).
            result: The search result to format.

        Returns:
            Formatted string like:
            [1] Document: "Title" (chunk 3)
            Content here...
        """
        title = result.document_title or "Untitled"
        return (
            f"[{index}] Document: \"{title}\" (chunk {result.chunk_index})\n"
            f"{result.content}"
        )
