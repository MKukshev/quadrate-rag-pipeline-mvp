import uuid
import pathlib
import time
from copy import deepcopy
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile, BackgroundTasks, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services import config
from services.categories import (
    DOC_TYPE_UNSTRUCTURED,
    extract_doc_types_from_text,
    guess_doc_type,
    normalize_doc_type,
)
from services.chunking import split_markdown
from services.embeddings import embed, get_embedder
from services.fusion import mmr, rrf
from services.keyword_index import add_chunks as kw_add, search as kw_search
from services.cache import ask_cache, search_cache
from services.text_cleaning import clean_chunk
from services.metrics import record_search, record_ask, snapshot as metrics_snapshot
from services import rerank
from services.parsers import (
    parse_csv_bytes,
    parse_docx_bytes,
    parse_pdf_bytes,
    parse_txt_bytes,
    parse_xlsx_bytes,
)
from services.qdrant_store import (
    client as qdrant_client,
    ensure_collection,
    semantic_search,
    upsert_chunks,
)
from services.rag import build_prompt, call_llm
from services.summarization import summarize_document_by_id, summarize_chunks, summarize_document_streaming
from services.llm_config import get_current_model_config
from services.summary_store import (
    save_document_summary,
    get_document_summary,
    has_document_summary,
    delete_document_summary,
    list_documents_without_summary,
    get_summary_stats,
    update_main_collection_summary_flag,
)
from services.thread_parser import parse_email_thread, parse_telegram_chat, parse_whatsapp_chat
from services.thread_store import (
    save_chat_message,
    get_thread_messages,
    save_thread_summary,
    get_thread_summary,
    list_threads,
    delete_thread,
)
from services.thread_summarization import summarize_thread, summarize_thread_from_messages

app = FastAPI(title="AI Assistant MVP (offline)")


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_time = datetime.now()
        start_time = time.time()

        if request.url.path not in ["/health", "/metrics"]:
            print(f"\n{'🌐 '*40}", flush=True)
            print(f"[HTTP REQUEST ⬇️ ] {request.method} {request.url.path}", flush=True)
            print(f"  ⏰ Request time: {request_time.strftime('%H:%M:%S.%f')[:-3]}", flush=True)
            print(f"  📍 Client: {request.client.host if request.client else 'unknown'}", flush=True)
            if request.query_params:
                print(f"  🔍 Query params: {dict(request.query_params)}", flush=True)
            print(f"{'─'*80}", flush=True)

        response = await call_next(request)

        elapsed = time.time() - start_time
        response_time = datetime.now()

        if request.url.path not in ["/health", "/metrics"]:
            print(f"{'─'*80}", flush=True)
            print(f"[HTTP RESPONSE ⬆️ ] {request.method} {request.url.path}", flush=True)
            print(f"  ✅ Status: {response.status_code}", flush=True)
            print(f"  ⏱️  Total HTTP time: {elapsed:.3f}s", flush=True)
            print(f"  ⏰ Response time: {response_time.strftime('%H:%M:%S.%f')[:-3]}", flush=True)
            print(f"{'🌐 '*40}\n", flush=True)

        response.headers["X-Process-Time"] = f"{elapsed:.3f}"
        return response


app.add_middleware(TimingMiddleware)


@app.on_event("startup")
def _startup():
    ensure_collection()
    get_embedder()


def _parse(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return parse_pdf_bytes(data)
    if name.endswith(".docx"):
        return parse_docx_bytes(data)
    if name.endswith(".xlsx"):
        return parse_xlsx_bytes(data)
    if name.endswith(".csv"):
        return parse_csv_bytes(data)
    if name.endswith(".txt") or name.endswith(".md"):
        return parse_txt_bytes(data)
    raise HTTPException(status_code=400, detail=f"Формат {filename} не поддерживается")


class AskRequest(BaseModel):
    q: str
    space_id: Optional[str] = None
    top_k: int = config.TOP_K_DEFAULT
    doc_types: Optional[List[str]] = None
    mode: str = "auto"  # "auto" | "normal" | "summarize" | "detailed"


class SummarizeRequest(BaseModel):
    doc_id: str
    space_id: str
    focus: Optional[str] = None


class ChatMessageRequest(BaseModel):
    thread_id: str
    space_id: str
    sender: str
    text: str
    recipients: Optional[List[str]] = None
    chat_type: str = "user_chat"
    metadata: Optional[Dict] = None


class ThreadSummarizeRequest(BaseModel):
    thread_id: str
    space_id: str
    extract_action_items: bool = True
    extract_decisions: bool = True
    extract_topics: bool = True
    focus: Optional[str] = None


@app.post("/ingest")
async def ingest(
    space_id: str = Form(...),
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(None),
    generate_summary: bool = Form(False),
    background_tasks: BackgroundTasks = None,
):
    ext = pathlib.Path(file.filename).suffix.lower()
    if ext not in config.ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Расширение {ext} не поддерживается")
    data = await file.read()
    text = _parse(file.filename, data)
    chunks = split_markdown(text)
    cleaned_chunks: List[str] = []
    seen_chunks = set()
    for chunk in chunks:
        cleaned = clean_chunk(chunk)
        if not cleaned:
            continue
        if len(cleaned.split()) < 5:
            continue
        key = cleaned.lower()
        if key in seen_chunks:
            continue
        seen_chunks.add(key)
        cleaned_chunks.append(cleaned)
    chunks = cleaned_chunks
    doc_id = f"{pathlib.Path(file.filename).stem}_{uuid.uuid4().hex[:8]}"
    if not chunks:
        raise HTTPException(status_code=400, detail="Текст не извлечён/пустой")
    norm_doc_type = normalize_doc_type(doc_type) or guess_doc_type(
        text, file.filename, pathlib.Path(file.filename)
    )
    upsert_chunks(space_id, doc_id, norm_doc_type, chunks)
    kw_add(space_id, doc_id, norm_doc_type, chunks)
    
    # Асинхронная генерация summary
    if generate_summary and background_tasks:
        print(f"[Ingest] Scheduling background summarization for {doc_id}")
        background_tasks.add_task(
            _generate_and_save_summary_task,
            doc_id=doc_id,
            space_id=space_id,
            doc_type=norm_doc_type,
            num_chunks=len(chunks)
        )
    
    return {
        "doc_id": doc_id,
        "space_id": space_id,
        "doc_type": norm_doc_type,
        "chunks_indexed": len(chunks),
        "summary_pending": generate_summary,
    }


@app.get("/search")
def search(
    q: str,
    space_id: Optional[str] = None,
    top_k: int = config.TOP_K_DEFAULT,
    doc_types: Optional[List[str]] = Query(None),
):
    start = time.perf_counter()
    norm_doc_types = _normalize_doc_types(doc_types, q)
    effective_top_k = _determine_top_k(top_k, norm_doc_types, q)
    cache_key = None
    if config.CACHE_ENABLED:
        cache_key = _search_cache_key(q, space_id, norm_doc_types, effective_top_k)
        cached = search_cache.get(cache_key)
        if cached is not None:
            if isinstance(cached, tuple):
                cached_response, cached_tokens = cached
            else:
                cached_response = cached
                cached_tokens = _count_context_tokens(cached_response.get("results", []))
            response = deepcopy(cached_response)
            latency_ms = (time.perf_counter() - start) * 1000
            record_search(latency_ms, cached_tokens, True)
            return response
    sem = semantic_search(q, space_id, norm_doc_types, effective_top_k)
    lex = kw_search(q, space_id, norm_doc_types, effective_top_k)
    pool_top_k = min(config.CONTEXT_MAX_CHUNKS * 2, effective_top_k * (config.MMR_CANDIDATE_MULTIPLIER if config.MMR_ENABLED else 1))
    candidate_pool = rrf(sem, lex, top_k=pool_top_k)
    candidate_pool = rerank.apply_rerank(q, candidate_pool)
    mmr_selected = _apply_mmr(candidate_pool, q, effective_top_k)
    fused = _limit_one_chunk_per_doc(mmr_selected, candidate_pool, effective_top_k)
    response = {
        "query": q,
        "space_id": space_id,
        "doc_types": norm_doc_types,
        "results": fused,
        "semantic_only": sem,
        "bm25_only": lex,
    }
    context_tokens = _count_context_tokens(fused)
    latency_ms = (time.perf_counter() - start) * 1000
    record_search(latency_ms, context_tokens, False)
    if cache_key is not None:
        search_cache.set(cache_key, (deepcopy(response), context_tokens))
    return response


@app.post("/ask")
async def ask(req: AskRequest = Body(...)):
    start = time.perf_counter()
    norm_doc_types = _normalize_doc_types(req.doc_types, req.q)
    requested_top_k = req.top_k or config.TOP_K_DEFAULT
    effective_top_k = _determine_top_k(requested_top_k, norm_doc_types, req.q)
    cache_key = None
    if config.CACHE_ENABLED:
        cache_key = _ask_cache_key(req.q, req.space_id, norm_doc_types, effective_top_k)
        cached = ask_cache.get(cache_key)
        if cached is not None:
            if isinstance(cached, tuple):
                cached_response, ctx_tokens, ans_tokens = cached
            else:
                cached_response = cached
                ctx_tokens = 0
                ans_tokens = 0
            response = deepcopy(cached_response)
            latency_ms = (time.perf_counter() - start) * 1000
            if ctx_tokens == 0:
                ctx_tokens = _count_context_tokens(response.get("sources", []))
            record_ask(latency_ms, ctx_tokens, ans_tokens, True)
            return response
    sem = semantic_search(req.q, req.space_id, norm_doc_types, effective_top_k)
    lex = kw_search(req.q, req.space_id, norm_doc_types, effective_top_k)
    pool_top_k = effective_top_k * (config.MMR_CANDIDATE_MULTIPLIER if config.MMR_ENABLED else 1)
    candidate_pool = rrf(sem, lex, top_k=pool_top_k)
    candidate_pool = rerank.apply_rerank(req.q, candidate_pool)
    mmr_selected = _apply_mmr(candidate_pool, req.q, effective_top_k)
    fused = _limit_one_chunk_per_doc(mmr_selected, candidate_pool, effective_top_k)
    
    # Smart context compression с режимами работы
    context_tokens = _count_context_tokens(fused)
    model_config = get_current_model_config()
    use_summarization = False
    
    # Валидация и нормализация режима
    valid_modes = ["auto", "normal", "summarize", "detailed"]
    if req.mode not in valid_modes:
        print(f"[RAG] Invalid mode '{req.mode}', using default 'auto'")
        req.mode = "auto"
    
    # Определение нужна ли суммаризация на основе режима
    if req.mode == "summarize":
        # Принудительная суммаризация
        should_summarize = True
        print(f"[RAG] Mode: summarize (forced). Context: {context_tokens} tokens")
    elif req.mode in ["normal", "detailed"]:
        # Никогда не суммаризировать
        should_summarize = False
        print(f"[RAG] Mode: {req.mode} (no summarization). Context: {context_tokens} tokens")
    else:  # mode == "auto"
        # Автоматическое решение на основе порога модели
        should_summarize = context_tokens > model_config.summarization_threshold
        if should_summarize:
            print(f"[RAG] Mode: auto. Context {context_tokens} tokens > threshold {model_config.summarization_threshold}. Using summarization.")
        else:
            print(f"[RAG] Mode: auto. Context {context_tokens} tokens ≤ threshold {model_config.summarization_threshold}. Using normal RAG.")
    
    if should_summarize:
        try:
            summary = await summarize_chunks(
                fused,
                query=req.q,
                max_output_tokens=model_config.summarization_max_output
            )
            
            # Построить промпт с суммаризированным контекстом
            prompt = (
                "Ты — ассистент, отвечай строго по предоставленному КОНТЕКСТУ. "
                "Если данных недостаточно — так и скажи.\n\n"
                f"КОНТЕКСТ (суммаризировано из {len(fused)} найденных фрагментов):\n{summary}\n\n"
                f"ВОПРОС:\n{req.q}\n\n"
                "Ответь кратко и по делу. Если перечисляешь дедлайны — укажи дату и источник."
            )
            use_summarization = True
            
        except Exception as e:
            # Fallback: если суммаризация не удалась - используем обычный промпт
            print(f"[RAG] Summarization failed: {e}. Falling back to normal prompt.")
            prompt = build_prompt(fused, req.q)
    else:
        # Обычный RAG без суммаризации
        prompt = build_prompt(fused, req.q)
    
    answer = call_llm(prompt)
    sources = [
        {
            "doc_id": r["payload"].get("doc_id"),
            "chunk_index": r["payload"].get("chunk_index"),
            "doc_type": r["payload"].get("doc_type", DOC_TYPE_UNSTRUCTURED),
        }
        for r in fused
    ]
    response = {
        "answer": answer,
        "sources": sources,
        "summarized": use_summarization,  # Индикатор использования суммаризации
        "context_tokens": context_tokens,  # Размер исходного контекста
        "mode": req.mode,  # Режим работы (auto/normal/summarize/detailed)
        "model": config.LLM_MODEL,  # Какая модель использовалась
    }
    answer_tokens = _count_answer_tokens(answer)
    latency_ms = (time.perf_counter() - start) * 1000
    record_ask(latency_ms, context_tokens, answer_tokens, False)
    if cache_key is not None and not answer.startswith("[LLM ошибка"):
        ask_cache.set(cache_key, (deepcopy(response), context_tokens, answer_tokens))
    return response


@app.post("/summarize")
async def summarize_document(req: SummarizeRequest = Body(...)):
    """
    Суммаризировать документ по doc_id
    
    Сначала проверяет наличие сохраненного summary.
    Если нет - генерирует на лету.
    """
    try:
        # Проверить есть ли уже сохраненный summary
        cached_summary = get_document_summary(req.doc_id, req.space_id)
        
        if cached_summary and not req.focus:
            # Использовать кэшированный summary (если нет фокуса)
            print(f"[Summarize] Using cached summary for {req.doc_id}")
            return {
                "doc_id": req.doc_id,
                "space_id": req.space_id,
                "summary": cached_summary["summary"],
                "chunks_processed": cached_summary.get("original_chunks", 0),
                "focus": req.focus,
                "cached": True,
                "generated_at": cached_summary.get("generated_at"),
            }
        
        # Генерировать на лету
        from services.qdrant_store import client
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        # Получить все чанки документа
        results = client().scroll(
            collection_name=config.QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="doc_id", match=MatchValue(value=req.doc_id)),
                    FieldCondition(key="space_id", match=MatchValue(value=req.space_id)),
                ]
            ),
            limit=1000
        )
        
        if not results[0]:
            raise HTTPException(
                status_code=404,
                detail=f"Document {req.doc_id} not found in space {req.space_id}"
            )
        
        # Суммаризация
        print(f"[Summarize] Generating on-the-fly summary for {req.doc_id}")
        summary = await summarize_document_by_id(req.doc_id, req.space_id, req.focus)
        
        # Сохранить в кэш только если нет фокуса
        if not req.focus:
            save_document_summary(
                doc_id=req.doc_id,
                space_id=req.space_id,
                summary=summary,
                original_chunks=len(results[0]),
                summary_tokens=len(summary.split())
            )
            print(f"[Summarize] Summary saved to cache for {req.doc_id}")
        
        return {
            "doc_id": req.doc_id,
            "space_id": req.space_id,
            "summary": summary,
            "chunks_processed": len(results[0]),
            "focus": req.focus,
            "cached": False,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Summarization failed: {str(e)}"
        )


@app.post("/summarize-stream")
async def summarize_document_stream(req: SummarizeRequest = Body(...)):
    """
    Потоковая суммаризация документа (SSE)
    
    Возвращает Server-Sent Events с прогрессом генерации.
    Показывает:
    - Прогресс обработки
    - Промежуточные результаты
    - ETA (estimated time)
    - Финальный summary
    """
    import json
    
    async def generate_events():
        try:
            # Проверить кэш
            cached = get_document_summary(req.doc_id, req.space_id)
            
            if cached and not req.focus:
                # Вернуть кэшированный summary сразу
                event_data = {
                    'type': 'cached',
                    'summary': cached['summary'],
                    'progress': 100,
                    'generated_at': cached.get('generated_at')
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                return
            
            # Streaming суммаризация
            async for event in summarize_document_streaming(req.doc_id, req.space_id, req.focus):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.post("/summarize-poll")
async def summarize_document_poll(
    req: SummarizeRequest = Body(...),
    background_tasks: BackgroundTasks = None
):
    """
    Long polling fallback для браузеров без SSE поддержки
    
    Запускает суммаризацию в фоне и возвращает task_id.
    Клиент затем poll'ит статус через GET /summarize-status/{task_id}
    """
    # Проверить кэш
    cached = get_document_summary(req.doc_id, req.space_id)
    
    if cached and not req.focus:
        return {
            "status": "complete",
            "summary": cached['summary'],
            "cached": True
        }
    
    # Создать task_id
    task_id = f"{req.doc_id}_{uuid.uuid4().hex[:8]}"
    
    # Запустить в фоне (simplified version - в production используйте Celery/Redis)
    # Для демо просто вернем инструкцию использовать SSE
    return {
        "status": "pending",
        "task_id": task_id,
        "message": "Long polling not fully implemented. Please use /summarize-stream for real-time progress.",
        "recommendation": "Use Server-Sent Events endpoint: POST /summarize-stream"
    }


def _generate_and_save_summary_task(
    doc_id: str,
    space_id: str,
    doc_type: str,
    num_chunks: int
):
    """
    Background task для генерации и сохранения summary
    """
    import asyncio
    try:
        print(f"[Background] Starting summarization for {doc_id}")
        
        # Генерировать summary
        summary = asyncio.run(summarize_document_by_id(doc_id, space_id, focus=None))
        
        # Сохранить в отдельной коллекции
        summary_id = save_document_summary(
            doc_id=doc_id,
            space_id=space_id,
            summary=summary,
            doc_type=doc_type,
            original_chunks=num_chunks
        )
        
        # Обновить флаг в основной коллекции
        update_main_collection_summary_flag(doc_id, space_id, summary_id)
        
        print(f"[Background] Summary saved for {doc_id}, id={summary_id}")
        
    except Exception as e:
        print(f"[Background] Summarization failed for {doc_id}: {e}")


@app.get("/health")
def health():
    """Lightweight health probe for container orchestration and manual checks."""
    qdrant_ok, qdrant_detail = True, "ok"
    try:
        qdrant_client().get_collections()
    except Exception as e:
        qdrant_ok, qdrant_detail = False, str(e)

    embedder_ok, embedder_dim = True, None
    try:
        embedder_dim = get_embedder().get_sentence_embedding_dimension()
    except Exception as e:
        embedder_ok, embedder_dim = False, str(e)

    llm_ok, llm_mode = True, config.LLM_MODE
    if config.LLM_MODE == "ollama":
        try:
            import requests

            r = requests.get("http://ollama:11434/api/tags", timeout=2)
            r.raise_for_status()
        except Exception as e:
            llm_ok = False
            llm_mode = f"ollama: {e}"

    status = "ok" if (qdrant_ok and embedder_ok and llm_ok) else "degraded"
    return {
        "status": status,
        "components": {
            "qdrant": {"ok": qdrant_ok, "detail": qdrant_detail},
            "embedder": {
                "ok": embedder_ok,
                "dimension": embedder_dim,
                "model": config.EMBED_MODEL,
            },
            "llm": {"ok": llm_ok, "mode": llm_mode, "model": config.LLM_MODEL},
            "keyword_index_dir": str(config.KEYWORD_INDEX_DIR),
        },
        "metrics": metrics_snapshot(),
    }


@app.get("/metrics")
def metrics_endpoint():
    return metrics_snapshot()


@app.get("/model-config")
def get_model_configuration():
    """
    Получить конфигурацию текущей LLM модели
    
    Показывает параметры модели: context window, пороги суммаризации, и т.д.
    """
    model_config = get_current_model_config()
    
    return {
        "model_name": model_config.model_name,
        "provider": model_config.provider,
        "context_window": model_config.context_window,
        "max_output_tokens": model_config.max_output_tokens,
        "effective_context_for_rag": model_config.effective_context_for_rag,
        "summarization_threshold": model_config.summarization_threshold,
        "summarization_max_output": model_config.summarization_max_output,
        "recommended_chunk_limit": model_config.recommended_chunk_limit,
        "tokens_per_second": model_config.tokens_per_second,
        "supports_streaming": model_config.supports_streaming,
        "supports_function_calling": model_config.supports_function_calling,
        "description": model_config.description,
        "recommended_use_cases": model_config.recommended_use_cases,
    }


@app.get("/documents/{doc_id}/summary-status")
def get_summary_status(doc_id: str, space_id: str = Query(...)):
    """
    Проверить наличие summary для документа
    """
    summary_info = get_document_summary(doc_id, space_id)
    
    if summary_info:
        return {
            "doc_id": doc_id,
            "space_id": space_id,
            "has_summary": True,
            "summary_preview": summary_info["summary"][:200] + "..." if len(summary_info["summary"]) > 200 else summary_info["summary"],
            "summary_tokens": summary_info.get("summary_tokens"),
            "generated_at": summary_info.get("generated_at"),
            "model": summary_info.get("model"),
        }
    else:
        return {
            "doc_id": doc_id,
            "space_id": space_id,
            "has_summary": False,
        }


@app.post("/documents/{doc_id}/regenerate-summary")
def regenerate_summary(
    doc_id: str,
    space_id: str = Query(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Пересоздать summary для документа
    
    Полезно если:
    - Модель LLM изменилась
    - Нужно обновить summary
    """
    from services.qdrant_store import client
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    # Проверить существование документа
    results = client().scroll(
        collection_name=config.QDRANT_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=1
    )
    
    if not results[0]:
        raise HTTPException(404, f"Document {doc_id} not found")
    
    doc_type = results[0][0].payload.get("doc_type")
    num_chunks = len(results[0])
    
    if background_tasks:
        # Асинхронная регенерация
        print(f"[API] Scheduling summary regeneration for {doc_id}")
        background_tasks.add_task(
            _generate_and_save_summary_task,
            doc_id=doc_id,
            space_id=space_id,
            doc_type=doc_type,
            num_chunks=num_chunks
        )
        return {
            "doc_id": doc_id,
            "space_id": space_id,
            "status": "pending",
            "message": "Summary regeneration scheduled"
        }
    else:
        # Синхронная регенерация
        summary = summarize_document_by_id(doc_id, space_id)
        summary_id = save_document_summary(
            doc_id=doc_id,
            space_id=space_id,
            summary=summary,
            doc_type=doc_type,
            original_chunks=num_chunks
        )
        update_main_collection_summary_flag(doc_id, space_id, summary_id)
        
        return {
            "doc_id": doc_id,
            "space_id": space_id,
            "status": "completed",
            "summary": summary
        }


@app.post("/bulk-summarize")
def bulk_summarize(
    space_id: str = Query(...),
    doc_types: Optional[List[str]] = Query(None),
    limit: int = Query(100),
    background_tasks: BackgroundTasks = None,
):
    """
    Массовая суммаризация документов в space
    
    Суммаризирует все документы которые еще не имеют summary.
    """
    # Найти документы без summary
    docs_without_summary = list_documents_without_summary(space_id, doc_types, limit)
    
    if not docs_without_summary:
        return {
            "space_id": space_id,
            "documents_to_process": 0,
            "message": "All documents already have summaries"
        }
    
    # Запустить суммаризацию для каждого документа
    from services.qdrant_store import client
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    for doc_id in docs_without_summary:
        # Получить метаданные документа
        results = client().scroll(
            collection_name=config.QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                    FieldCondition(key="space_id", match=MatchValue(value=space_id)),
                ]
            ),
            limit=1000
        )
        
        if results[0]:
            doc_type = results[0][0].payload.get("doc_type")
            num_chunks = len(results[0])
            
            if background_tasks:
                background_tasks.add_task(
                    _generate_and_save_summary_task,
                    doc_id=doc_id,
                    space_id=space_id,
                    doc_type=doc_type,
                    num_chunks=num_chunks
                )
    
    return {
        "space_id": space_id,
        "documents_to_process": len(docs_without_summary),
        "doc_ids": docs_without_summary,
        "status": "scheduled" if background_tasks else "processing"
    }


@app.get("/summary-stats")
def summary_statistics(space_id: Optional[str] = Query(None)):
    """
    Статистика по сохраненным summaries
    """
    stats = get_summary_stats(space_id)
    return stats


@app.delete("/documents/{doc_id}/summary")
def delete_summary(doc_id: str, space_id: str = Query(...)):
    """
    Удалить summary для документа
    """
    deleted = delete_document_summary(doc_id, space_id)
    
    if deleted:
        return {
            "doc_id": doc_id,
            "space_id": space_id,
            "status": "deleted"
        }
    else:
        raise HTTPException(404, f"Summary not found for document {doc_id}")


# ===== Thread / Conversation Endpoints =====

@app.post("/chat/message")
def post_chat_message(req: ChatMessageRequest = Body(...)):
    """
    Сохранить сообщение в чат-тред
    
    Для пользовательских чатов в приложении.
    Сообщения сохраняются в отдельную коллекцию с thread_id.
    """
    try:
        message_id = save_chat_message(
            thread_id=req.thread_id,
            space_id=req.space_id,
            sender=req.sender,
            text=req.text,
            recipients=req.recipients,
            chat_type=req.chat_type,
            metadata=req.metadata
        )
        
        return {
            "message_id": message_id,
            "thread_id": req.thread_id,
            "space_id": req.space_id,
            "status": "saved"
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to save message: {str(e)}")


@app.get("/chat/thread/{thread_id}/messages")
def get_chat_thread_messages(
    thread_id: str,
    space_id: str = Query(...),
    limit: int = Query(1000),
    offset: int = Query(0)
):
    """
    Получить все сообщения треда
    """
    try:
        messages = get_thread_messages(thread_id, space_id, limit, offset)
        
        return {
            "thread_id": thread_id,
            "space_id": space_id,
            "message_count": len(messages),
            "messages": messages
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get messages: {str(e)}")


@app.post("/thread/summarize")
async def summarize_chat_thread(req: ThreadSummarizeRequest = Body(...)):
    """
    Суммаризировать чат-тред с извлечением структурированной информации
    
    Автоматически извлекает:
    - Базовую суммаризацию разговора
    - Action items (задачи, TODO)
    - Decisions (принятые решения)
    - Topics (обсуждаемые темы)
    - Участников и хронологию
    """
    try:
        # Получить сообщения треда
        messages = get_thread_messages(req.thread_id, req.space_id)
        
        if not messages:
            raise HTTPException(404, f"Thread {req.thread_id} not found or has no messages")
        
        # Определить тип чата
        chat_type = messages[0].get("chat_type", "user_chat")
        
        # Суммаризировать
        result = await summarize_thread_from_messages(
            messages,
            chat_type=chat_type,
            extract_action_items=req.extract_action_items,
            extract_decisions=req.extract_decisions,
            extract_topics=req.extract_topics,
            focus=req.focus
        )
        
        # Сохранить summary
        save_thread_summary(
            thread_id=req.thread_id,
            space_id=req.space_id,
            summary=result["summary"],
            chat_type=result["thread_type"],
            participants=result["participants"],
            message_count=result["message_count"],
            start_date=result["start_date"],
            end_date=result["end_date"],
            action_items=result.get("action_items", []),
            decisions=result.get("decisions", []),
            topics=result.get("topics", [])
        )
        
        return {
            "thread_id": req.thread_id,
            "space_id": req.space_id,
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Thread summarization failed: {str(e)}")


@app.get("/thread/{thread_id}/summary")
def get_chat_thread_summary(thread_id: str, space_id: str = Query(...)):
    """
    Получить сохраненную суммаризацию треда
    """
    summary = get_thread_summary(thread_id, space_id)
    
    if not summary:
        raise HTTPException(404, f"Summary not found for thread {thread_id}")
    
    return {
        "thread_id": thread_id,
        "space_id": space_id,
        **summary
    }


@app.post("/ingest-thread")
async def ingest_thread_file(
    space_id: str = Form(...),
    file: UploadFile = File(...),
    thread_type: str = Form("email"),
    auto_summarize: bool = Form(True),
    background_tasks: BackgroundTasks = None
):
    """
    Загрузить и проиндексировать файл с email/chat тредом
    
    Поддерживаемые форматы:
    - email: .txt с email тредом
    - telegram: Telegram export
    - whatsapp: WhatsApp export
    
    Автоматически:
    - Парсит структуру треда
    - Сохраняет сообщения в chat_messages
    - Опционально генерирует summary
    """
    try:
        data = await file.read()
        text = data.decode('utf-8', errors='ignore')
        
        # Парсить thread
        if thread_type == "email":
            thread = parse_email_thread(text)
        elif thread_type == "telegram":
            thread = parse_telegram_chat(text)
        elif thread_type == "whatsapp":
            thread = parse_whatsapp_chat(text)
        else:
            raise HTTPException(400, f"Unsupported thread_type: {thread_type}")
        
        # Создать thread_id
        thread_id = f"{pathlib.Path(file.filename).stem}_{uuid.uuid4().hex[:8]}"
        
        # Сохранить сообщения
        for msg in thread.messages:
            save_chat_message(
                thread_id=thread_id,
                space_id=space_id,
                sender=msg.sender,
                text=msg.text,
                recipients=msg.recipients,
                message_timestamp=msg.date,
                chat_type=f"{thread_type}_thread",
                metadata={
                    "subject": msg.subject,
                    "message_id": msg.message_id,
                    "reply_to": msg.reply_to
                }
            )
        
        # Опционально суммаризировать
        if auto_summarize and background_tasks:
            background_tasks.add_task(
                _summarize_thread_background,
                thread_id=thread_id,
                space_id=space_id,
                thread=thread
            )
        
        return {
            "thread_id": thread_id,
            "space_id": space_id,
            "thread_type": f"{thread_type}_thread",
            "messages": len(thread.messages),
            "participants": thread.participants,
            "start_date": thread.start_date.isoformat(),
            "end_date": thread.end_date.isoformat(),
            "summary_pending": auto_summarize
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Thread ingestion failed: {str(e)}")


@app.get("/threads")
def list_all_threads(
    space_id: str = Query(...),
    chat_type: Optional[str] = Query(None),
    limit: int = Query(100)
):
    """
    Список всех тредов в space
    """
    try:
        threads = list_threads(space_id, chat_type, limit)
        
        return {
            "space_id": space_id,
            "thread_count": len(threads),
            "threads": threads
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to list threads: {str(e)}")


@app.delete("/thread/{thread_id}")
def delete_chat_thread(thread_id: str, space_id: str = Query(...)):
    """
    Удалить тред (сообщения + summary)
    """
    try:
        deleted = delete_thread(thread_id, space_id)
        
        if deleted:
            return {
                "thread_id": thread_id,
                "space_id": space_id,
                "status": "deleted"
            }
        else:
            raise HTTPException(404, f"Thread {thread_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to delete thread: {str(e)}")


async def _summarize_thread_background(thread_id: str, space_id: str, thread):
    """Background task для суммаризации треда"""
    try:
        print(f"[Background] Summarizing thread {thread_id}")
        
        result = await summarize_thread(thread)
        
        save_thread_summary(
            thread_id=thread_id,
            space_id=space_id,
            summary=result["summary"],
            chat_type=result["thread_type"],
            participants=result["participants"],
            message_count=result["message_count"],
            start_date=result["start_date"],
            end_date=result["end_date"],
            action_items=result.get("action_items", []),
            decisions=result.get("decisions", []),
            topics=result.get("topics", [])
        )
        
        print(f"[Background] Thread summary saved for {thread_id}")
        
    except Exception as e:
        print(f"[Background] Thread summarization failed: {e}")


def _normalize_doc_types(values: Optional[List[str]], fallback_text: Optional[str]) -> Optional[List[str]]:
    normalized: List[str] = []
    if not values and config.AUTO_DOC_TYPES:
        auto = extract_doc_types_from_text(fallback_text)
        values = auto or None
    if not values:
        return None
    for value in values:
        norm = normalize_doc_type(value)
        if norm and norm not in normalized:
            normalized.append(norm)
    return normalized or None


def _determine_top_k(requested: Optional[int], doc_types: Optional[List[str]], query: Optional[str]) -> int:
    base = requested or config.TOP_K_DEFAULT
    tokens = len((query or "").split())
    doc_types = doc_types or []
    target = base
    if doc_types and len(doc_types) <= 1 and tokens <= 5:
        target = min(target, config.TOP_K_MIN)
    elif not doc_types or tokens >= 10:
        target = max(target, config.TOP_K_MAX)
    target = max(config.TOP_K_MIN, target)
    target = min(target, config.CONTEXT_MAX_CHUNKS)
    return max(1, target)


def _apply_mmr(results: List[Dict], query: str, top_k: int) -> List[Dict]:
    if not config.MMR_ENABLED:
        return results[:top_k]
    if not results:
        return results

    query_vec = embed(query)

    def _embed_text(text: str):
        snippet = (text or "")[:1000]
        return embed(snippet) if snippet else []

    selected = mmr(query_vec, results, top_k=top_k, lambda_mult=config.MMR_LAMBDA, embed_text=_embed_text)
    if len(selected) < top_k:
        remaining = [r for r in results if r not in selected]
        selected.extend(remaining[: max(0, top_k - len(selected))])
    return selected[:top_k]


def _limit_one_chunk_per_doc(selected: List[Dict], pool: List[Dict], top_k: int) -> List[Dict]:
    if not config.ONE_CHUNK_PER_DOC:
        return selected[:top_k]
    seen: Dict[str, int] = {}
    unique: List[Dict] = []
    duplicates_by_doc: Dict[str, List[Dict]] = {}
    others: List[Dict] = []

    for item in selected:
        payload = item.get("payload") or {}
        doc_id = payload.get("doc_id")
        chunk_idx = payload.get("chunk_index")
        if doc_id and doc_id not in seen:
            seen[doc_id] = chunk_idx if isinstance(chunk_idx, int) else 0
            unique.append(item)
        else:
            if doc_id:
                duplicates_by_doc.setdefault(doc_id, []).append(item)
            else:
                others.append(item)

    if len(unique) >= top_k:
        return unique[:top_k]

    for item in pool:
        if len(unique) >= top_k:
            break
        payload = item.get("payload") or {}
        doc_id = payload.get("doc_id")
        if doc_id and doc_id not in seen:
            seen[doc_id] = payload.get("chunk_index") if isinstance(payload.get("chunk_index"), int) else 0
            unique.append(item)

    if len(unique) >= top_k:
        return unique[:top_k]

    neighbor_candidates: List[Dict] = []
    for doc_id, dup_items in duplicates_by_doc.items():
        if doc_id not in seen:
            neighbor_candidates.extend(dup_items)
            continue
        primary_idx = seen[doc_id]
        neighbor_candidates.extend(
            sorted(
                dup_items,
                key=lambda it: abs(((it.get("payload") or {}).get("chunk_index") or 0) - primary_idx),
            )
        )

    for item in pool:
        payload = item.get("payload") or {}
        doc_id = payload.get("doc_id")
        if not doc_id or doc_id not in seen:
            continue
        if item in unique or item in neighbor_candidates:
            continue
        neighbor_candidates.append(item)

    for item in neighbor_candidates + others:
        if len(unique) >= top_k:
            break
        if item in unique:
            continue
        unique.append(item)

    return unique[:top_k]

def _normalized_doc_type_key(doc_types: Optional[List[str]]) -> Tuple:
    if not doc_types:
        return ("__all__",)
    cleaned = [dt for dt in doc_types if dt]
    return tuple(sorted(cleaned)) or ("__all__",)


def _search_cache_key(query: str, space_id: Optional[str], doc_types: Optional[List[str]], top_k: int) -> Tuple:
    return (
        "search",
        query.strip(),
        space_id or "__all__",
        _normalized_doc_type_key(doc_types),
        top_k,
        config.MMR_ENABLED,
        round(config.MMR_LAMBDA, 3),
        config.MMR_CANDIDATE_MULTIPLIER,
    )


def _ask_cache_key(query: str, space_id: Optional[str], doc_types: Optional[List[str]], top_k: int) -> Tuple:
    return (
        "ask",
        query.strip(),
        space_id or "__all__",
        _normalized_doc_type_key(doc_types),
        top_k,
        config.LLM_MODEL,
        config.LLM_MAX_TOKENS,
    )


def _count_context_tokens(items: List[Dict]) -> int:
    total = 0
    for item in items:
        payload = item.get("payload") if isinstance(item, dict) else None
        if not payload:
            continue
        text = payload.get("text") or ""
        total += len(text.split())
    return total


def _count_answer_tokens(answer: str) -> int:
    if not answer:
        return 0
    return len(answer.split())
