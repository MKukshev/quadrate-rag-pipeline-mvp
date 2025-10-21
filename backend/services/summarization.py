"""
Document Summarization Service
Provides map-reduce summarization for large documents that exceed context limits
"""

import asyncio
from typing import List, Dict, Optional
from .rag import call_llm
from .chunking import split_markdown
from . import config


def count_tokens_simple(text: str) -> int:
    """Simple token counter (approximation)"""
    return len(text.split())


def split_text_by_tokens(text: str, max_tokens: int = 8000, overlap: int = 500) -> List[str]:
    """
    Split text into chunks by token count
    
    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk
        overlap: Token overlap between chunks
        
    Returns:
        List of text chunks
    """
    # Use existing split_markdown with custom params
    return split_markdown(text, target_tokens=max_tokens, overlap=overlap)


async def summarize_text(text: str, max_summary_tokens: int = 500, focus: Optional[str] = None) -> str:
    """
    Summarize text using LLM (single pass)
    
    Args:
        text: Text to summarize
        max_summary_tokens: Maximum tokens in summary
        focus: Optional focus area for summarization
        
    Returns:
        Summary text
    """
    focus_instruction = f"\nFocus specifically on: {focus}" if focus else ""
    
    prompt = f"""Summarize the following text concisely in approximately {max_summary_tokens} words or less.
Preserve key facts, numbers, dates, and important details.{focus_instruction}

TEXT:
{text}

SUMMARY:"""
    
    summary = call_llm(prompt)
    
    # Remove common LLM artifacts
    if summary.startswith("[LLM"):
        return summary  # Error message, return as-is
    
    return summary.strip()


async def summarize_long_text(
    text: str,
    chunk_size: int = 8000,
    chunk_overlap: int = 500,
    focus: Optional[str] = None
) -> str:
    """
    Map-Reduce summarization for long texts
    
    Args:
        text: Long text to summarize
        chunk_size: Size of chunks for MAP phase
        chunk_overlap: Overlap between chunks
        focus: Optional focus area
        
    Returns:
        Final summary
    """
    tokens = count_tokens_simple(text)
    
    # If short enough, direct summarization
    if tokens < chunk_size:
        return await summarize_text(text, max_summary_tokens=500, focus=focus)
    
    print(f"[Summarization] Document is large ({tokens} tokens). Starting Map-Reduce...")
    
    # MAP PHASE: Split and summarize each chunk
    chunks = split_text_by_tokens(text, max_tokens=chunk_size, overlap=chunk_overlap)
    print(f"[Summarization] Split into {len(chunks)} chunks")
    
    summaries = []
    for i, chunk in enumerate(chunks, 1):
        print(f"[Summarization] Processing chunk {i}/{len(chunks)}...")
        
        summary = await summarize_text(
            chunk,
            max_summary_tokens=300,  # Each chunk → ~300 words
            focus=focus
        )
        
        if not summary.startswith("[LLM"):
            summaries.append(f"Part {i}: {summary}")
    
    if not summaries:
        return "[Summarization failed: no chunks could be processed]"
    
    print(f"[Summarization] MAP phase complete. Generated {len(summaries)} summaries")
    
    # REDUCE PHASE: Combine summaries
    combined = "\n\n".join(summaries)
    combined_tokens = count_tokens_simple(combined)
    
    # If combined summaries are short enough, return as-is
    if combined_tokens < chunk_size:
        print(f"[Summarization] REDUCE phase: Combined summary is {combined_tokens} tokens")
        return combined
    
    # Otherwise, do a final summarization
    print(f"[Summarization] REDUCE phase: Combining {len(summaries)} summaries...")
    
    final_prompt = f"""Create a comprehensive summary from these partial summaries.
Preserve all key facts, numbers, dates, and important details.

PARTIAL SUMMARIES:
{combined}

FINAL SUMMARY:"""
    
    final_summary = call_llm(final_prompt)
    print(f"[Summarization] Complete!")
    
    return final_summary


async def summarize_chunks(
    chunks: List[Dict],
    query: Optional[str] = None,
    max_output_tokens: int = 1000
) -> str:
    """
    Summarize multiple search result chunks
    Useful when you have many relevant chunks but limited context window
    
    Args:
        chunks: List of search result chunks (from hybrid search)
        query: Original user query (to focus summarization)
        max_output_tokens: Maximum tokens in output
        
    Returns:
        Summarized context
    """
    # Extract text from chunks
    texts = []
    for chunk in chunks:
        payload = chunk.get("payload", {})
        text = payload.get("text", "")
        doc_id = payload.get("doc_id", "unknown")
        chunk_idx = payload.get("chunk_index", 0)
        
        # Add source info
        texts.append(f"[Source: {doc_id} chunk {chunk_idx}]\n{text}")
    
    combined = "\n\n---\n\n".join(texts)
    
    # Summarize with focus on query
    return await summarize_long_text(
        combined,
        chunk_size=8000,
        focus=query
    )


async def summarize_document_by_id(
    doc_id: str,
    space_id: str,
    focus: Optional[str] = None
) -> str:
    """
    Summarize entire document by doc_id
    Retrieves all chunks and creates comprehensive summary
    
    Args:
        doc_id: Document ID
        space_id: Space ID
        focus: Optional focus area
        
    Returns:
        Document summary
    """
    from .qdrant_store import client
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    # Get all chunks of the document
    results = client().scroll(
        collection_name=config.QDRANT_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=1000  # Max chunks per document
    )
    
    if not results[0]:
        return f"[Error: Document {doc_id} not found]"
    
    # Sort chunks by index
    sorted_chunks = sorted(
        results[0],
        key=lambda x: x.payload.get("chunk_index", 0)
    )
    
    # Combine all chunks
    full_text = "\n\n".join([
        chunk.payload.get("text", "")
        for chunk in sorted_chunks
    ])
    
    # Summarize
    return await summarize_long_text(full_text, focus=focus)


# Synchronous wrappers for FastAPI (if needed)
def summarize_text_sync(text: str, max_summary_tokens: int = 500, focus: Optional[str] = None) -> str:
    """Synchronous version of summarize_text"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(summarize_text(text, max_summary_tokens, focus))
    finally:
        loop.close()


def summarize_long_text_sync(text: str, chunk_size: int = 8000, focus: Optional[str] = None) -> str:
    """Synchronous version of summarize_long_text"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(summarize_long_text(text, chunk_size, focus=focus))
    finally:
        loop.close()

