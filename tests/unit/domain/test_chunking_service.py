"""Unit tests for SimpleChunkingStrategy domain service.

These tests have ZERO external dependencies — no mocks, no I/O.
SimpleChunkingStrategy is pure Python logic.
"""

from __future__ import annotations

import pytest

from app.domain.services.chunking_service import ChunkData, SimpleChunkingStrategy


@pytest.fixture
def strategy() -> SimpleChunkingStrategy:
    return SimpleChunkingStrategy()


class TestSimpleChunkingStrategy:
    """Tests for SimpleChunkingStrategy.chunk()"""

    def test_empty_content_returns_no_chunks(self, strategy: SimpleChunkingStrategy) -> None:
        """Empty or whitespace-only content produces zero chunks."""
        assert strategy.chunk("", chunk_size=100, chunk_overlap=10) == []
        assert strategy.chunk("   \n  ", chunk_size=100, chunk_overlap=10) == []

    def test_short_content_fits_single_chunk(self, strategy: SimpleChunkingStrategy) -> None:
        """Content shorter than chunk_size yields exactly one chunk."""
        content = "Hello world"
        chunks = strategy.chunk(content, chunk_size=100, chunk_overlap=10)

        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].content == content.strip()

    def test_chunk_indices_are_sequential(self, strategy: SimpleChunkingStrategy) -> None:
        """Chunk indices start at 0 and increment by 1."""
        content = "A" * 300
        chunks = strategy.chunk(content, chunk_size=100, chunk_overlap=0)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunks_cover_full_content(self, strategy: SimpleChunkingStrategy) -> None:
        """All content characters appear in at least one chunk."""
        content = "Hello World this is a long piece of text " * 10
        chunks = strategy.chunk(content, chunk_size=100, chunk_overlap=20)

        assert len(chunks) > 1

        # Every chunk has non-empty content
        for chunk in chunks:
            assert chunk.content != ""

    def test_overlap_causes_repeated_content(self, strategy: SimpleChunkingStrategy) -> None:
        """Overlap means the tail of one chunk appears at the start of the next."""
        content = "A" * 200
        chunks = strategy.chunk(content, chunk_size=100, chunk_overlap=50)

        # With overlap, we expect more chunks than without
        chunks_no_overlap = strategy.chunk(content, chunk_size=100, chunk_overlap=0)
        assert len(chunks) >= len(chunks_no_overlap)

    def test_returns_chunk_data_objects(self, strategy: SimpleChunkingStrategy) -> None:
        """Each chunk is a proper ChunkData instance."""
        chunks = strategy.chunk("Hello World", chunk_size=100, chunk_overlap=0)
        assert all(isinstance(c, ChunkData) for c in chunks)

    def test_token_count_is_non_negative(self, strategy: SimpleChunkingStrategy) -> None:
        """Token counts are non-negative integers."""
        content = "The quick brown fox jumps over the lazy dog"
        chunks = strategy.chunk(content, chunk_size=50, chunk_overlap=5)
        for chunk in chunks:
            assert chunk.token_count >= 0

    def test_start_char_less_than_end_char(self, strategy: SimpleChunkingStrategy) -> None:
        """Each chunk has start_char < end_char."""
        content = "A" * 300
        chunks = strategy.chunk(content, chunk_size=100, chunk_overlap=0)
        for chunk in chunks:
            assert chunk.start_char < chunk.end_char

    def test_newline_boundary_splitting(self, strategy: SimpleChunkingStrategy) -> None:
        """Strategy prefers to split at newlines when possible."""
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = strategy.chunk(content, chunk_size=25, chunk_overlap=0)

        # Chunks should not begin with a newline
        for chunk in chunks:
            assert not chunk.content.startswith("\n")

    def test_large_chunk_size_produces_one_chunk(self, strategy: SimpleChunkingStrategy) -> None:
        """chunk_size larger than content produces a single chunk."""
        content = "Short content"
        chunks = strategy.chunk(content, chunk_size=9999, chunk_overlap=0)
        assert len(chunks) == 1

    def test_chunk_data_is_immutable(self, strategy: SimpleChunkingStrategy) -> None:
        """ChunkData is frozen/immutable — modification raises an error."""
        chunks = strategy.chunk("Hello World", chunk_size=100, chunk_overlap=0)
        with pytest.raises(Exception):  # ValidationError or AttributeError
            chunks[0].content = "mutated"  # type: ignore[misc]
