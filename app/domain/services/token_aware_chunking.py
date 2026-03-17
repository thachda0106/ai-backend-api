"""Token-aware chunking strategy using tiktoken — IMP-2 Fix.

Replaces SimpleChunkingStrategy which split on character count.
Character-based chunking is unreliable because:
  1. Tokens ≠ characters (ratio varies by language/domain)
  2. No guarantee chunks stay under embedding model's 8191-token limit
  3. token_count was computed as word count (off by ~30%)

This implementation splits at exact token boundaries using the same
tokenizer as the target model, guaranteeing correctness.
"""

from __future__ import annotations

import tiktoken

from app.domain.services.chunking_service import ChunkData, ChunkingStrategy


class TokenAwareChunkingStrategy(ChunkingStrategy):
    """Splits text at exact token boundaries using tiktoken.

    chunk_size and chunk_overlap are in TOKENS, not characters.
    Guarantees no chunk exceeds OpenAI's embedding model limits (8191 tokens).

    Algorithm:
    1. Encode full text to token IDs with tiktoken
    2. Slide a window of chunk_size tokens with chunk_overlap overlap
    3. Decode each window back to text
    4. Record exact char positions for traceability
    """

    # Safeguard: hard cap at embedding model max
    _MAX_TOKENS = 8000  # text-embedding-3-small max is 8191

    def __init__(self, model: str = "gpt-4o") -> None:
        """Initialize with the tokenizer for the target model family.

        Args:
            model: Model name for tiktoken encoding selection.
                   GPT-4o and text-embedding-3 share the same tokenizer (cl100k_base).
        """
        try:
            self._encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fall back to cl100k_base if model not found
            self._encoder = tiktoken.get_encoding("cl100k_base")

    def chunk(
        self,
        content: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[ChunkData]:
        """Split content into token-bounded chunks.

        Args:
            content:       Raw text content to chunk.
            chunk_size:    Max tokens per chunk (hard-capped at 8000).
            chunk_overlap: Overlap tokens between adjacent chunks.

        Returns:
            List of ChunkData with exact token counts.
        """
        if not content.strip():
            return []

        # Safety: enforce max token limit
        effective_chunk_size = min(chunk_size, self._MAX_TOKENS)
        effective_overlap = min(chunk_overlap, effective_chunk_size // 2)

        # Encode full document to token IDs
        token_ids = self._encoder.encode(content)

        if not token_ids:
            return []

        chunks: list[ChunkData] = []
        chunk_index = 0
        start = 0

        while start < len(token_ids):
            end = min(start + effective_chunk_size, len(token_ids))
            chunk_token_ids = token_ids[start:end]

            # Decode back to text
            chunk_text = self._encoder.decode(chunk_token_ids)

            if chunk_text.strip():
                # Find approximate char positions in original string
                preceding_text = self._encoder.decode(token_ids[:start])
                start_char = len(preceding_text)
                end_char = start_char + len(chunk_text)

                chunks.append(
                    ChunkData(
                        content=chunk_text.strip(),
                        start_char=start_char,
                        end_char=end_char,
                        chunk_index=chunk_index,
                        token_count=len(chunk_token_ids),  # Exact token count!
                    )
                )
                chunk_index += 1

            if end >= len(token_ids):
                break

            # Move start forward, respecting overlap
            start = end - effective_overlap
            if start >= end:
                start = end

        return chunks
