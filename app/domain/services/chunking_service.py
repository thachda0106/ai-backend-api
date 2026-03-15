"""Chunking strategy domain service."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class ChunkData(BaseModel):
    """Output from the chunking process.

    Frozen (immutable) — chunk data is produced once and never modified.
    """

    model_config = ConfigDict(frozen=True)

    content: str
    start_char: int
    end_char: int
    chunk_index: int
    token_count: int


class ChunkingStrategy(ABC):
    """Abstract interface for document chunking strategies.

    Implementations may use simple text splitting, semantic chunking,
    or any other strategy for breaking documents into chunks.
    """

    @abstractmethod
    def chunk(
        self,
        content: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[ChunkData]:
        """Split content into chunks.

        Args:
            content: The text content to chunk.
            chunk_size: Maximum size of each chunk in characters.
            chunk_overlap: Number of overlapping characters between chunks.

        Returns:
            List of ChunkData with position information.
        """


class SimpleChunkingStrategy(ChunkingStrategy):
    """Simple text chunking by character count with overlap.

    Splits text at newline boundaries where possible,
    falling back to character-level splitting.
    """

    def chunk(
        self,
        content: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[ChunkData]:
        """Split content into overlapping chunks.

        The algorithm:
        1. Split by newlines to get natural paragraphs/lines
        2. Accumulate lines until chunk_size is reached
        3. Create chunk with overlap from previous chunk
        """
        if not content.strip():
            return []

        chunks: list[ChunkData] = []
        start = 0
        chunk_index = 0

        while start < len(content):
            # Calculate end position
            end = min(start + chunk_size, len(content))

            # Try to break at a newline boundary (look backward from end)
            if end < len(content):
                newline_pos = content.rfind("\n", start, end)
                if newline_pos > start:
                    end = newline_pos + 1  # Include the newline

            chunk_content = content[start:end].strip()

            if chunk_content:
                chunks.append(
                    ChunkData(
                        content=chunk_content,
                        start_char=start,
                        end_char=end,
                        chunk_index=chunk_index,
                        token_count=len(chunk_content.split()),  # Rough word-based estimate
                    )
                )
                chunk_index += 1

            # Move start forward, accounting for overlap
            start = end - chunk_overlap if end < len(content) else end

            # Prevent infinite loop
            if start >= end:
                start = end

        return chunks
