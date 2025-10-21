"""
Document Summarization Service
Provides map-reduce summarization for large documents that exceed context limits
"""

import asyncio
import time
from typing import List, Dict, Optional, AsyncGenerator
from .rag import call_llm
from .chunking import split_markdown
from . import config
from .llm_config import get_current_model_config


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


async def summarize_document_streaming(
    doc_id: str,
    space_id: str,
    focus: Optional[str] = None
) -> AsyncGenerator[Dict, None]:
    """
    Progressive streaming summarization with detailed progress
    
    Yields events:
    - type: "start" - начало процесса
    - type: "processing" - обработка
    - type: "progress" - прогресс Map фазы
    - type: "partial_summary" - промежуточный результат чанка
    - type: "reduce" - фаза объединения
    - type: "summary" - финальный summary
    - type: "complete" - завершение
    """
    from services.qdrant_store import client
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    start_time = time.time()
    model_config = get_current_model_config()
    
    # Получить все чанки документа
    results = client().scroll(
        collection_name=config.QDRANT_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=1000,
        with_payload=True,
        with_vectors=False
    )
    
    if not results[0]:
        yield {
            "type": "error",
            "message": f"Document {doc_id} not found"
        }
        return
    
    chunks = results[0]
    texts = [c.payload.get("text", "") for c in chunks]
    combined_text = "\n\n".join(texts)
    total_tokens = count_tokens_simple(combined_text)
    
    # Определить стратегию
    threshold = 8000
    
    if total_tokens <= threshold:
        # Простая суммаризация
        yield {
            "type": "start",
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "strategy": "simple",
            "progress": 0
        }
        
        yield {
            "type": "processing",
            "stage": "simple",
            "progress": 30,
            "message": f"Generating summary for document ({total_tokens} tokens)...",
            "eta_seconds": int(total_tokens / model_config.tokens_per_second)
        }
        
        # Генерировать summary
        chunk_start = time.time()
        summary = await summarize_text(combined_text, max_summary_tokens=2000, focus=focus)
        chunk_time = time.time() - chunk_start
        
        yield {
            "type": "summary",
            "text": summary,
            "progress": 100,
            "tokens": count_tokens_simple(summary),
            "processing_time": round(chunk_time, 2)
        }
        
        yield {
            "type": "complete",
            "progress": 100,
            "total_time": round(time.time() - start_time, 2)
        }
        
    else:
        # Map-Reduce стратегия
        num_map_chunks = (total_tokens // 6000) + 1
        
        yield {
            "type": "start",
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "strategy": "map_reduce",
            "map_chunks": num_map_chunks,
            "progress": 0
        }
        
        yield {
            "type": "processing",
            "stage": "map_reduce",
            "progress": 5,
            "message": f"Large document ({total_tokens} tokens). Using Map-Reduce with {num_map_chunks} chunks...",
            "eta_seconds": int((total_tokens / model_config.tokens_per_second) * 1.5)  # Map-Reduce overhead
        }
        
        # MAP фаза
        chunk_summaries = []
        tokens_per_chunk = 6000
        
        for i in range(num_map_chunks):
            start_idx = int(i * tokens_per_chunk * 0.85)  # 15% overlap
            end_idx = int(min((i + 1) * tokens_per_chunk, len(combined_text)))
            
            # Найти границу предложения
            if end_idx < len(combined_text):
                next_period = combined_text.find('. ', end_idx)
                if next_period != -1 and next_period < end_idx + 200:
                    end_idx = next_period + 1
            
            chunk_text = combined_text[start_idx:end_idx].strip()
            chunk_tokens = count_tokens_simple(chunk_text)
            
            # Оценка оставшегося времени
            remaining_chunks = num_map_chunks - i
            avg_tokens_per_chunk = chunk_tokens
            eta = int((remaining_chunks * avg_tokens_per_chunk / model_config.tokens_per_second) + 5)  # +5s для reduce
            
            yield {
                "type": "progress",
                "stage": "map",
                "current": i + 1,
                "total": num_map_chunks,
                "progress": 10 + int(60 * (i + 1) / num_map_chunks),
                "message": f"Processing chunk {i+1}/{num_map_chunks} ({chunk_tokens} tokens)...",
                "eta_seconds": eta
            }
            
            # Суммаризировать чанк
            chunk_start = time.time()
            chunk_summary = await summarize_text(
                chunk_text,
                max_summary_tokens=800,
                focus=focus
            )
            chunk_time = time.time() - chunk_start
            
            chunk_summaries.append(chunk_summary)
            
            # Отдать промежуточный результат
            preview_length = 150
            yield {
                "type": "partial_summary",
                "chunk": i + 1,
                "summary": chunk_summary[:preview_length] + "..." if len(chunk_summary) > preview_length else chunk_summary,
                "full_summary": chunk_summary,
                "tokens": count_tokens_simple(chunk_summary),
                "processing_time": round(chunk_time, 2)
            }
            
            # Небольшая пауза для клиента
            await asyncio.sleep(0.1)
        
        # REDUCE фаза
        yield {
            "type": "progress",
            "stage": "reduce",
            "progress": 75,
            "message": f"Combining {len(chunk_summaries)} summaries...",
            "eta_seconds": int(sum(count_tokens_simple(s) for s in chunk_summaries) / model_config.tokens_per_second)
        }
        
        # Объединить summaries
        combined_summaries = "\n\n".join([
            f"Section {i+1}:\n{summary}"
            for i, summary in enumerate(chunk_summaries)
        ])
        
        reduce_prompt = f"""Combine these section summaries into one coherent, comprehensive summary.
Maintain key information and structure.

{combined_summaries}
"""
        
        if focus:
            reduce_prompt += f"\n\nFocus on: {focus}"
        
        reduce_start = time.time()
        final_summary = await summarize_text(
            reduce_prompt,
            max_summary_tokens=model_config.summarization_max_output,
            focus=None  # Focus уже в промпте
        )
        reduce_time = time.time() - reduce_start
        
        yield {
            "type": "summary",
            "text": final_summary,
            "progress": 100,
            "tokens": count_tokens_simple(final_summary),
            "map_chunks": num_map_chunks,
            "processing_time": round(reduce_time, 2)
        }
        
        yield {
            "type": "complete",
            "progress": 100,
            "total_time": round(time.time() - start_time, 2),
            "tokens_processed": total_tokens
        }

