"""Text chunking utilities."""

from dataclasses import dataclass
from typing import Optional

import tiktoken


@dataclass
class ChunkInfo:
    """Information about a text chunk."""

    content: str
    chunk_index: int
    start_offset: int
    end_offset: int
    token_count: int
    page_numbers: Optional[list[int]] = None


class TextChunker:
    """Fixed-size text chunker with overlap."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        """Initialize chunker.

        Args:
            chunk_size: Target tokens per chunk
            chunk_overlap: Overlap tokens between chunks
            encoding_name: Tiktoken encoding name
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))

    def chunk_text(
        self,
        text: str,
        page_boundaries: Optional[list[tuple[int, int]]] = None,
    ) -> list[ChunkInfo]:
        """Chunk text into fixed-size pieces.

        Args:
            text: Text to chunk
            page_boundaries: Optional list of (start_offset, page_number) tuples

        Returns:
            List of ChunkInfo objects
        """
        if not text.strip():
            return []

        # Tokenize
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)

        if total_tokens <= self.chunk_size:
            # Single chunk
            return [
                ChunkInfo(
                    content=text,
                    chunk_index=0,
                    start_offset=0,
                    end_offset=len(text),
                    token_count=total_tokens,
                    page_numbers=self._get_pages_for_range(
                        0, len(text), page_boundaries
                    ),
                )
            ]

        chunks = []
        chunk_index = 0
        token_start = 0

        while token_start < total_tokens:
            # Calculate token end
            token_end = min(token_start + self.chunk_size, total_tokens)

            # Decode chunk tokens
            chunk_tokens = tokens[token_start:token_end]
            chunk_text = self.encoding.decode(chunk_tokens)

            # Calculate character offsets (approximate)
            # Decode up to token_start to get start offset
            start_offset = len(self.encoding.decode(tokens[:token_start]))
            end_offset = start_offset + len(chunk_text)

            # Get page numbers for this range
            page_numbers = self._get_pages_for_range(
                start_offset, end_offset, page_boundaries
            )

            chunks.append(
                ChunkInfo(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    token_count=len(chunk_tokens),
                    page_numbers=page_numbers,
                )
            )

            # Move start with overlap
            token_start = token_end - self.chunk_overlap
            if token_start >= total_tokens:
                break

            # Prevent infinite loop on small overlap
            if token_end == total_tokens:
                break

            chunk_index += 1

        return chunks

    def _get_pages_for_range(
        self,
        start: int,
        end: int,
        page_boundaries: Optional[list[tuple[int, int]]],
    ) -> Optional[list[int]]:
        """Get page numbers that overlap with a character range.

        Args:
            start: Start character offset
            end: End character offset
            page_boundaries: List of (start_offset, page_number)

        Returns:
            List of page numbers or None
        """
        if not page_boundaries:
            return None

        pages = set()
        for i, (boundary_start, page_num) in enumerate(page_boundaries):
            # Get end of this page
            if i + 1 < len(page_boundaries):
                boundary_end = page_boundaries[i + 1][0]
            else:
                boundary_end = float("inf")

            # Check if ranges overlap
            if boundary_start < end and boundary_end > start:
                pages.add(page_num)

        return sorted(pages) if pages else None


class SemanticChunker:
    """Semantic chunker that respects sentence/paragraph boundaries."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        """Initialize chunker.

        Args:
            chunk_size: Target tokens per chunk
            chunk_overlap: Overlap tokens between chunks
            encoding_name: Tiktoken encoding name
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    def chunk_text(
        self,
        text: str,
        page_boundaries: Optional[list[tuple[int, int]]] = None,
    ) -> list[ChunkInfo]:
        """Chunk text semantically by paragraphs/sentences.

        Args:
            text: Text to chunk
            page_boundaries: Optional list of (start_offset, page_number)

        Returns:
            List of ChunkInfo objects
        """
        if not text.strip():
            return []

        # Split into paragraphs
        paragraphs = self._split_paragraphs(text)

        if not paragraphs:
            return []

        chunks = []
        current_content = ""
        current_start = 0
        chunk_index = 0

        for para_start, para_text in paragraphs:
            para_tokens = self.count_tokens(para_text)

            # If single paragraph is too large, use fixed chunking
            if para_tokens > self.chunk_size:
                # Flush current chunk first
                if current_content:
                    chunks.append(self._make_chunk(
                        current_content,
                        chunk_index,
                        current_start,
                        page_boundaries,
                    ))
                    chunk_index += 1
                    current_content = ""

                # Fixed chunk the large paragraph
                fixed_chunker = TextChunker(
                    self.chunk_size, self.chunk_overlap, "cl100k_base"
                )
                sub_chunks = fixed_chunker.chunk_text(para_text, page_boundaries)
                for sub_chunk in sub_chunks:
                    sub_chunk.chunk_index = chunk_index
                    sub_chunk.start_offset += para_start
                    sub_chunk.end_offset += para_start
                    chunks.append(sub_chunk)
                    chunk_index += 1

                current_start = para_start + len(para_text)
                continue

            # Check if adding paragraph exceeds chunk size
            combined = current_content + ("\n\n" if current_content else "") + para_text
            combined_tokens = self.count_tokens(combined)

            if combined_tokens > self.chunk_size and current_content:
                # Flush current chunk
                chunks.append(self._make_chunk(
                    current_content,
                    chunk_index,
                    current_start,
                    page_boundaries,
                ))
                chunk_index += 1

                # Start new chunk with overlap
                if self.chunk_overlap > 0:
                    # Take last paragraph as overlap
                    current_content = para_text
                    current_start = para_start
                else:
                    current_content = para_text
                    current_start = para_start
            else:
                if not current_content:
                    current_start = para_start
                current_content = combined

        # Don't forget the last chunk
        if current_content:
            chunks.append(self._make_chunk(
                current_content,
                chunk_index,
                current_start,
                page_boundaries,
            ))

        return chunks

    def _split_paragraphs(self, text: str) -> list[tuple[int, str]]:
        """Split text into paragraphs with their starting offsets.

        Args:
            text: Text to split

        Returns:
            List of (start_offset, paragraph_text)
        """
        paragraphs = []
        current_pos = 0

        # Split on double newlines
        parts = text.split("\n\n")

        for part in parts:
            part = part.strip()
            if part:
                # Find actual position in original text
                start = text.find(part, current_pos)
                if start >= 0:
                    paragraphs.append((start, part))
                    current_pos = start + len(part)

        return paragraphs

    def _make_chunk(
        self,
        content: str,
        chunk_index: int,
        start_offset: int,
        page_boundaries: Optional[list[tuple[int, int]]],
    ) -> ChunkInfo:
        """Create a ChunkInfo object.

        Args:
            content: Chunk content
            chunk_index: Index of the chunk
            start_offset: Character start offset
            page_boundaries: Page boundary information

        Returns:
            ChunkInfo object
        """
        end_offset = start_offset + len(content)
        token_count = self.count_tokens(content)

        # Get page numbers
        page_numbers = None
        if page_boundaries:
            pages = set()
            for i, (boundary_start, page_num) in enumerate(page_boundaries):
                if i + 1 < len(page_boundaries):
                    boundary_end = page_boundaries[i + 1][0]
                else:
                    boundary_end = float("inf")

                if boundary_start < end_offset and boundary_end > start_offset:
                    pages.add(page_num)

            page_numbers = sorted(pages) if pages else None

        return ChunkInfo(
            content=content,
            chunk_index=chunk_index,
            start_offset=start_offset,
            end_offset=end_offset,
            token_count=token_count,
            page_numbers=page_numbers,
        )


def get_chunker(strategy: str, chunk_size: int = 512, chunk_overlap: int = 50):
    """Get chunker by strategy name.

    Args:
        strategy: 'fixed' or 'semantic'
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks

    Returns:
        Chunker instance
    """
    if strategy == "semantic":
        return SemanticChunker(chunk_size, chunk_overlap)
    return TextChunker(chunk_size, chunk_overlap)
