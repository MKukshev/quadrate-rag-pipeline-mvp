"""
Example: Integration of summarization into existing app.py
Shows multiple integration points for summarization
"""

# Add to existing app.py:

from services.summarization import (
    summarize_text_sync,
    summarize_long_text_sync,
    summarize_chunks,
    summarize_document_by_id,
)
from pydantic import BaseModel
from typing import Optional


# ===== NEW ENDPOINT: Summarize Document =====

class SummarizeRequest(BaseModel):
    doc_id: str
    space_id: str
    focus: Optional[str] = None  # Optional: focus area for summarization


@app.post("/summarize")
def summarize_document(req: SummarizeRequest = Body(...)):
    """
    Summarize entire document by doc_id
    
    Use cases:
    - User wants TL;DR of a large document
    - Agent needs overview of document
    - Preview before full RAG
    """
    try:
        summary = summarize_document_by_id(
            doc_id=req.doc_id,
            space_id=req.space_id,
            focus=req.focus
        )
        
        return {
            "doc_id": req.doc_id,
            "summary": summary,
            "focus": req.focus
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")


# ===== INTEGRATION 1: Smart context compression in /ask =====

@app.post("/ask")
def ask_with_smart_compression(req: AskRequest = Body(...)):
    """
    Enhanced /ask with automatic summarization when context is too large
    """
    start = time.perf_counter()
    
    # ... existing search logic ...
    sem = semantic_search(req.q, req.space_id, norm_doc_types, effective_top_k)
    lex = kw_search(req.q, req.space_id, norm_doc_types, effective_top_k)
    candidate_pool = rrf(sem, lex, top_k=pool_top_k)
    fused = _limit_one_chunk_per_doc(candidate_pool, effective_top_k)
    
    # NEW: Check context size
    context_tokens = _count_context_tokens(fused)
    max_context = config.LLM_MAX_TOKENS * 3  # Rough estimate of model context
    
    if context_tokens > max_context:
        print(f"[Context too large] {context_tokens} tokens > {max_context}. Using summarization...")
        
        # Summarize chunks instead of using them directly
        summary = summarize_chunks(fused, query=req.q, max_output_tokens=2000)
        
        # Build prompt with summary instead of full chunks
        prompt = (
            "Ты — ассистент, отвечай строго по предоставленному КОНТЕКСТУ. "
            "Если данных недостаточно — так и скажи.\n\n"
            f"КОНТЕКСТ (summarized from {len(fused)} chunks):\n{summary}\n\n"
            f"ВОПРОС:\n{req.q}\n\n"
            "Ответь кратко и по делу."
        )
    else:
        # Normal RAG pipeline
        prompt = build_prompt(fused, req.q)
    
    answer = call_llm(prompt)
    # ... rest of the logic ...


# ===== INTEGRATION 2: Summarize mode in /ask =====

class AskRequestWithMode(AskRequest):
    mode: Optional[str] = "normal"  # "normal" | "summarize"


@app.post("/ask/v2")
def ask_with_mode(req: AskRequestWithMode = Body(...)):
    """
    Enhanced /ask with explicit summarize mode
    
    Modes:
    - normal: Standard RAG (return chunks + answer)
    - summarize: First summarize relevant docs, then answer
    """
    # ... search logic ...
    fused = _limit_one_chunk_per_doc(candidate_pool, effective_top_k)
    
    if req.mode == "summarize":
        # Explicitly summarize before answering
        summary = summarize_chunks(fused, query=req.q)
        
        prompt = f"""Based on this summary of relevant documents:

{summary}

Answer the following question:
{req.q}

Answer:"""
        
        answer = call_llm(prompt)
        
        return {
            "answer": answer,
            "summary": summary,  # Include summary in response
            "mode": "summarize",
            "sources": [...]
        }
    else:
        # Normal RAG
        prompt = build_prompt(fused, req.q)
        answer = call_llm(prompt)
        return {"answer": answer, "mode": "normal", "sources": [...]}


# ===== INTEGRATION 3: Email thread summarization =====

@app.get("/summarize/email-thread")
def summarize_email_thread(
    space_id: str,
    doc_type: str = "email_correspondence",
    topic: Optional[str] = None
):
    """
    Summarize all emails on a topic
    
    Example: GET /summarize/email-thread?space_id=acme&topic=migration
    """
    # Search for all emails on topic
    if topic:
        results = semantic_search(topic, space_id, [doc_type], top_k=50)
    else:
        # Get all emails
        results = semantic_search("*", space_id, [doc_type], top_k=100)
    
    if not results:
        return {"summary": "No emails found"}
    
    # Group by doc_id
    docs_map = {}
    for r in results:
        doc_id = r["payload"]["doc_id"]
        if doc_id not in docs_map:
            docs_map[doc_id] = []
        docs_map[doc_id].append(r["payload"]["text"])
    
    # Summarize each email thread
    thread_summaries = []
    for doc_id, chunks in docs_map.items():
        thread_text = "\n\n".join(chunks)
        summary = summarize_text_sync(thread_text, max_summary_tokens=200)
        thread_summaries.append({
            "doc_id": doc_id,
            "summary": summary
        })
    
    # Create final overview
    all_summaries = "\n\n".join([
        f"Thread {i+1} ({s['doc_id']}):\n{s['summary']}"
        for i, s in enumerate(thread_summaries)
    ])
    
    final_summary = summarize_text_sync(
        all_summaries,
        max_summary_tokens=500,
        focus=topic
    )
    
    return {
        "topic": topic,
        "threads_found": len(thread_summaries),
        "summary": final_summary,
        "thread_summaries": thread_summaries
    }


# ===== INTEGRATION 4: Summarize at ingestion time =====

@app.post("/ingest")
async def ingest_with_summarization(
    space_id: str = Form(...),
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(None),
    create_summary: bool = Form(False),  # NEW: flag to create summary
):
    """
    Enhanced /ingest with optional summarization at index time
    """
    # ... existing parsing logic ...
    text = _parse(file.filename, await file.read())
    chunks = split_markdown(text)
    
    # NEW: Create summary if requested or if document is large
    summary = None
    if create_summary or count_tokens_simple(text) > 5000:
        print(f"[Ingest] Creating summary for {file.filename}...")
        summary = summarize_text_sync(text, max_summary_tokens=500)
        
        # Store summary as a special chunk
        summary_chunk = f"[DOCUMENT SUMMARY]\n\n{summary}"
        chunks.insert(0, summary_chunk)  # First chunk is summary
    
    # ... existing indexing logic ...
    upsert_chunks(space_id, doc_id, norm_doc_type, chunks)
    
    return {
        "doc_id": doc_id,
        "chunks_indexed": len(chunks),
        "summary": summary,  # Include summary in response
        "has_summary": summary is not None
    }


# ===== INTEGRATION 5: Batch summarization =====

class BatchSummarizeRequest(BaseModel):
    space_id: str
    doc_ids: List[str]
    focus: Optional[str] = None


@app.post("/summarize/batch")
def batch_summarize(req: BatchSummarizeRequest = Body(...)):
    """
    Summarize multiple documents in batch
    
    Use case: Research bot needs overview of multiple docs
    """
    summaries = []
    
    for doc_id in req.doc_ids:
        try:
            summary = summarize_document_by_id(
                doc_id=doc_id,
                space_id=req.space_id,
                focus=req.focus
            )
            summaries.append({
                "doc_id": doc_id,
                "summary": summary,
                "status": "success"
            })
        except Exception as e:
            summaries.append({
                "doc_id": doc_id,
                "summary": None,
                "status": "failed",
                "error": str(e)
            })
    
    # Create overview from all summaries
    all_summaries_text = "\n\n".join([
        f"Document: {s['doc_id']}\n{s['summary']}"
        for s in summaries
        if s['status'] == 'success'
    ])
    
    overview = summarize_text_sync(
        all_summaries_text,
        max_summary_tokens=800,
        focus=req.focus
    )
    
    return {
        "overview": overview,
        "summaries": summaries,
        "total_documents": len(req.doc_ids),
        "successful": len([s for s in summaries if s['status'] == 'success'])
    }

