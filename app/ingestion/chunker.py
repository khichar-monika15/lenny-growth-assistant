"""
Semantic text chunker for transcript processing.
Chunks text into overlapping segments with token count limits.
"""
from dataclasses import dataclass
from typing import List
import tiktoken


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    content: str
    token_count: int
    start_char: int
    end_char: int
    chunk_index: int = 0


def chunk_text(
    text: str,
    min_tokens: int = 800,
    max_tokens: int = 1200,
    overlap_tokens: int = 200
) -> List[Chunk]:
    """
    Split text into semantically meaningful chunks with overlap.

    Args:
        text: Text to chunk
        min_tokens: Minimum tokens per chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Number of overlapping tokens between chunks

    Returns:
        List of Chunk objects
    """
    # Initialize tokenizer
    encoding = tiktoken.get_encoding("cl100k_base")

    # Encode entire text
    tokens = encoding.encode(text)
    total_tokens = len(tokens)

    # If text fits in one chunk, return it
    if total_tokens <= max_tokens:
        return [Chunk(
            content=text,
            token_count=total_tokens,
            start_char=0,
            end_char=len(text),
            chunk_index=0
        )]

    chunks = []
    chunk_index = 0
    start_token_idx = 0

    while start_token_idx < total_tokens:
        # Determine end of this chunk
        end_token_idx = min(start_token_idx + max_tokens, total_tokens)

        # Extract tokens for this chunk
        chunk_tokens = tokens[start_token_idx:end_token_idx]

        # Decode back to text
        chunk_text = encoding.decode(chunk_tokens)

        # Calculate character offsets (approximate)
        # This is a simple approach; more sophisticated methods exist
        chars_per_token = len(text) / total_tokens if total_tokens > 0 else 1
        start_char = int(start_token_idx * chars_per_token)
        end_char = int(end_token_idx * chars_per_token)

        # Create chunk
        chunk = Chunk(
            content=chunk_text,
            token_count=len(chunk_tokens),
            start_char=start_char,
            end_char=min(end_char, len(text)),
            chunk_index=chunk_index
        )
        chunks.append(chunk)

        # Move to next chunk with overlap
        start_token_idx = end_token_idx - overlap_tokens
        chunk_index += 1

        # Prevent infinite loop if overlap >= max_tokens
        if overlap_tokens >= max_tokens:
            break

    return chunks
