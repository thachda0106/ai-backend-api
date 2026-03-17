"""Context window management service — score threshold + token budget.

Fixes applied:
  - IMP-3: Score threshold filtering (default 0.72) rejects irrelevant chunks
  - IMP-12: max_context_tokens configurable from settings (default 20K, not 3K)
"""

from __future__ import annotations

from app.domain.entities.search_result import SearchResult
from app.domain.services.token_service import TokenService


class ContextService:
    """Manages context window token budgets for RAG.

    1. Filters results below score_threshold (noise rejection)
    2. Fits as many high-quality chunks as possible within the token budget
    3. Formats them as numbered citation blocks for LLM attribution
    """

    def __init__(
        self,
        token_service: TokenService,
        max_context_tokens: int = 20_000,
        score_threshold: float = 0.72,
    ) -> None:
        self._token_service = token_service
        self._max_context_tokens = max_context_tokens
        self._score_threshold = score_threshold

    def build_context(
        self,
        search_results: list[SearchResult],
        model: str = "gpt-4o",
    ) -> tuple[str, list[SearchResult]]:
        """Build context string from relevant search results within token budget.

        Args:
            search_results: List of SearchResult ordered by score (highest first).
            model:          LLM model name for token counting.

        Returns:
            Tuple of (formatted context string, list of actually used results).
            Returns ("", []) if no results pass the score threshold.
        """
        if not search_results:
            return "", []

        # IMP-3: Filter out low-relevance results before injecting into prompt
        relevant = [r for r in search_results if r.score >= self._score_threshold]

        if not relevant:
            return "", []

        used_results: list[SearchResult] = []
        blocks: list[str] = []
        current_tokens = 0

        # IMP-12: Use configurable token budget (default 20K, not hard-coded 3K)
        for i, result in enumerate(relevant):
            block = self._format_block(i + 1, result)
            block_tokens = self._token_service.count_tokens(block, model)

            if current_tokens + block_tokens > self._max_context_tokens:
                break

            blocks.append(block)
            used_results.append(result)
            current_tokens += block_tokens

        context = "\n\n".join(blocks)
        return context, used_results

    @staticmethod
    def _format_block(index: int, result: SearchResult) -> str:
        """Format a search result as a numbered citation block."""
        title = result.document_title or "Untitled"
        score_pct = f"{result.score:.0%}"
        return (
            f"[{index}] Source: \"{title}\" "
            f"(chunk {result.chunk_index}, relevance {score_pct})\n"
            f"{result.content}"
        )
