"""
Example: FastAPI app with integrated Access Control
Shows how to integrate ACL into existing RAG pipeline
"""

import uuid
import pathlib
import time
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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

# Import ACL services
from services.access_control import (
    AccessContext,
    AccessControlService,
    AgentRole,
    UserRole,
    Visibility,
    augment_payload_with_access_control,
    create_context_for_user,
    create_context_for_agent,
)
from services.qdrant_store_with_acl import (
    ensure_collection,
    upsert_chunks_with_acl,
    semantic_search_with_acl,
    delete_by_doc,
    get_user_documents,
    update_document_access,
)
from services.rag import build_prompt, call_llm

app = FastAPI(title="AI Assistant MVP with Access Control")
security = HTTPBearer()


# Mock authentication - replace with real JWT validation
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    Extract user from JWT token
    In production: validate JWT, check expiration, get user from DB
    """
    token = credentials.credentials
    
    # Mock: parse token (in production use python-jose or similar)
    # Assuming format: "user_id|space_id|role"
    try:
        parts = token.split("|")
        return {
            "user_id": parts[0],
            "space_id": parts[1],
            "role": parts[2] if len(parts) > 2 else "member"
        }
    except:
        raise HTTPException(status_code=401, detail="Invalid authentication token")


def get_agent_context(agent_id: str, agent_role_name: str, space_id: str) -> AccessContext:
    """Helper to create agent context"""
    try:
        role = AgentRole(agent_role_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid agent role: {agent_role_name}")
    
    return create_context_for_agent(agent_id, role, space_id)


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
    channel_id: Optional[str] = None
    top_k: int = config.TOP_K_DEFAULT
    doc_types: Optional[List[str]] = None
    # Agent-specific fields
    agent_id: Optional[str] = None
    agent_role: Optional[str] = None


class DocumentAccessUpdate(BaseModel):
    doc_id: str
    visibility: Optional[str] = None
    access_list: Optional[List[str]] = None
    agent_roles: Optional[List[str]] = None


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    space_id: str = Form(...),
    channel_id: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    visibility: str = Form("team"),  # NEW: private|team|channel|public
    agent_roles: Optional[str] = Form(None),  # NEW: comma-separated roles
    security_level: int = Form(0),  # NEW: 0-5
    department: Optional[str] = Form(None),  # NEW
    current_user: Dict = Depends(get_current_user),
):
    """
    Ingest document with access control metadata
    
    New parameters:
    - visibility: Who can see this document (private/team/channel/public)
    - agent_roles: Comma-separated list of agent roles that can access (research,support,etc)
    - security_level: Confidentiality level 0-5
    - department: Department this document belongs to
    """
    # Validate user is in the space
    if current_user["space_id"] != space_id:
        raise HTTPException(status_code=403, detail="Access denied to this space")
    
    ext = pathlib.Path(file.filename).suffix.lower()
    if ext not in config.ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Расширение {ext} не поддерживается")
    
    data = await file.read()
    text = _parse(file.filename, data)
    chunks = split_markdown(text)
    
    # Clean chunks
    cleaned_chunks: List[str] = []
    seen_chunks = set()
    for chunk in chunks:
        cleaned = clean_chunk(chunk)
        if not cleaned or len(cleaned.split()) < 5:
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
    
    # Parse agent roles
    allowed_agent_roles = []
    if agent_roles:
        for role_name in agent_roles.split(","):
            role_name = role_name.strip()
            try:
                allowed_agent_roles.append(AgentRole(role_name))
            except ValueError:
                pass  # Ignore invalid roles
    
    if not allowed_agent_roles:
        # Default: allow research and analytics agents
        allowed_agent_roles = [AgentRole.RESEARCH, AgentRole.ANALYTICS]
    
    # Parse visibility
    try:
        vis = Visibility(visibility)
    except ValueError:
        vis = Visibility.TEAM
    
    # Create access control metadata
    access_metadata = augment_payload_with_access_control(
        base_payload={},
        owner_id=current_user["user_id"],
        visibility=vis,
        allowed_agent_roles=allowed_agent_roles,
        security_level=security_level,
        department=department,
    )
    
    # Upsert with ACL
    upsert_chunks_with_acl(
        space_id=space_id,
        doc_id=doc_id,
        doc_type=norm_doc_type,
        chunks=chunks,
        access_metadata=access_metadata,
        channel_id=channel_id,
    )
    
    # Also update keyword index (needs similar ACL integration)
    kw_add(space_id, doc_id, norm_doc_type, chunks)
    
    return {
        "doc_id": doc_id,
        "space_id": space_id,
        "channel_id": channel_id,
        "doc_type": norm_doc_type,
        "chunks_indexed": len(chunks),
        "visibility": visibility,
        "owner_id": current_user["user_id"],
        "allowed_agent_roles": [r.value for r in allowed_agent_roles],
    }


@app.get("/search")
def search(
    q: str,
    space_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    top_k: int = config.TOP_K_DEFAULT,
    doc_types: Optional[List[str]] = Query(None),
    # Agent mode
    agent_id: Optional[str] = Query(None),
    agent_role: Optional[str] = Query(None),
    current_user: Dict = Depends(get_current_user),
):
    """
    Search with access control
    
    For human users: uses current_user from JWT
    For agents: provide agent_id and agent_role query params
    """
    start = time.perf_counter()
    
    # Determine if this is an agent request
    if agent_id and agent_role:
        # Agent search
        context = get_agent_context(agent_id, agent_role, space_id or current_user["space_id"])
    else:
        # Human user search
        context = create_context_for_user(
            user_id=current_user["user_id"],
            space_id=space_id or current_user["space_id"],
            channel_id=channel_id,
        )
        # Set user role
        context.user_role = UserRole(current_user.get("role", "member"))
    
    norm_doc_types = _normalize_doc_types(doc_types, q)
    effective_top_k = _determine_top_k(top_k, norm_doc_types, q)
    
    # Semantic search with ACL
    sem = semantic_search_with_acl(q, context, norm_doc_types, effective_top_k)
    
    # Keyword search (would need similar ACL integration)
    lex = kw_search(q, space_id, norm_doc_types, effective_top_k)
    
    # Fusion
    pool_top_k = min(
        config.CONTEXT_MAX_CHUNKS * 2,
        effective_top_k * (config.MMR_CANDIDATE_MULTIPLIER if config.MMR_ENABLED else 1)
    )
    candidate_pool = rrf(sem, lex, top_k=pool_top_k)
    candidate_pool = rerank.apply_rerank(q, candidate_pool)
    mmr_selected = _apply_mmr(candidate_pool, q, effective_top_k)
    fused = _limit_one_chunk_per_doc(mmr_selected, candidate_pool, effective_top_k)
    
    # Filter out any results that shouldn't be accessible (defense in depth)
    acl_service = AccessControlService()
    filtered_results = [
        r for r in fused
        if acl_service.can_access_document(context, r["payload"])
    ]
    
    latency_ms = (time.perf_counter() - start) * 1000
    context_tokens = _count_context_tokens(filtered_results)
    record_search(latency_ms, context_tokens, False)
    
    return {
        "query": q,
        "space_id": context.space_id,
        "channel_id": context.channel_id,
        "doc_types": norm_doc_types,
        "results": filtered_results,
        "access_context": {
            "user_id": context.user_id,
            "agent_id": context.agent_id,
            "agent_role": context.agent_role.value if context.agent_role else None,
        }
    }


@app.post("/ask")
def ask(req: AskRequest = Body(...), current_user: Dict = Depends(get_current_user)):
    """
    RAG with access control
    """
    start = time.perf_counter()
    
    # Create context
    if req.agent_id and req.agent_role:
        context = get_agent_context(
            req.agent_id,
            req.agent_role,
            req.space_id or current_user["space_id"]
        )
    else:
        context = create_context_for_user(
            user_id=current_user["user_id"],
            space_id=req.space_id or current_user["space_id"],
            channel_id=req.channel_id,
        )
        context.user_role = UserRole(current_user.get("role", "member"))
    
    norm_doc_types = _normalize_doc_types(req.doc_types, req.q)
    effective_top_k = _determine_top_k(req.top_k or config.TOP_K_DEFAULT, norm_doc_types, req.q)
    
    # Search with ACL
    sem = semantic_search_with_acl(req.q, context, norm_doc_types, effective_top_k)
    lex = kw_search(req.q, req.space_id, norm_doc_types, effective_top_k)
    
    pool_top_k = effective_top_k * (config.MMR_CANDIDATE_MULTIPLIER if config.MMR_ENABLED else 1)
    candidate_pool = rrf(sem, lex, top_k=pool_top_k)
    candidate_pool = rerank.apply_rerank(req.q, candidate_pool)
    mmr_selected = _apply_mmr(candidate_pool, req.q, effective_top_k)
    fused = _limit_one_chunk_per_doc(mmr_selected, candidate_pool, effective_top_k)
    
    # Access control filter
    acl_service = AccessControlService()
    filtered = [r for r in fused if acl_service.can_access_document(context, r["payload"])]
    
    # RAG
    prompt = build_prompt(filtered, req.q)
    answer = call_llm(prompt)
    
    sources = [
        {
            "doc_id": r["payload"].get("doc_id"),
            "chunk_index": r["payload"].get("chunk_index"),
            "doc_type": r["payload"].get("doc_type", DOC_TYPE_UNSTRUCTURED),
            "visibility": r["payload"].get("visibility"),
            "owner_id": r["payload"].get("owner_id"),
        }
        for r in filtered
    ]
    
    context_tokens = _count_context_tokens(filtered)
    answer_tokens = _count_answer_tokens(answer)
    latency_ms = (time.perf_counter() - start) * 1000
    record_ask(latency_ms, context_tokens, answer_tokens, False)
    
    return {"answer": answer, "sources": sources}


@app.get("/my-documents")
def get_my_documents(
    space_id: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """Get all documents owned by current user"""
    docs = get_user_documents(
        user_id=current_user["user_id"],
        space_id=space_id or current_user["space_id"]
    )
    
    # Group by doc_id
    doc_map = {}
    for chunk in docs:
        doc_id = chunk.get("doc_id")
        if doc_id not in doc_map:
            doc_map[doc_id] = {
                "doc_id": doc_id,
                "doc_type": chunk.get("doc_type"),
                "visibility": chunk.get("visibility"),
                "security_level": chunk.get("security_level"),
                "chunks": 0
            }
        doc_map[doc_id]["chunks"] += 1
    
    return {"documents": list(doc_map.values())}


@app.post("/document-access")
def update_access(
    update: DocumentAccessUpdate = Body(...),
    current_user: Dict = Depends(get_current_user)
):
    """Update access control for a document"""
    context = create_context_for_user(
        user_id=current_user["user_id"],
        space_id=current_user["space_id"]
    )
    context.user_role = UserRole(current_user.get("role", "member"))
    
    # Build new access metadata
    new_metadata = {}
    if update.visibility:
        new_metadata["visibility"] = update.visibility
    if update.access_list is not None:
        new_metadata["access_list"] = update.access_list
    if update.agent_roles is not None:
        new_metadata["agent_roles"] = update.agent_roles
    
    try:
        update_document_access(update.doc_id, new_metadata, context)
        return {"status": "ok", "doc_id": update.doc_id}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.delete("/document/{doc_id}")
def delete_document(doc_id: str, current_user: Dict = Depends(get_current_user)):
    """Delete a document (only owner or admin)"""
    context = create_context_for_user(
        user_id=current_user["user_id"],
        space_id=current_user["space_id"]
    )
    context.user_role = UserRole(current_user.get("role", "member"))
    
    try:
        delete_by_doc(doc_id, context)
        return {"status": "deleted", "doc_id": doc_id}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.get("/health")
def health():
    """Health check"""
    return {"status": "ok", "features": ["access_control", "multi_tenant", "agent_roles"]}


@app.get("/metrics")
def metrics_endpoint():
    return metrics_snapshot()


# Helper functions (same as original)
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
    
    for item in selected:
        payload = item.get("payload") or {}
        doc_id = payload.get("doc_id")
        if doc_id and doc_id not in seen:
            seen[doc_id] = 0
            unique.append(item)
    
    return unique[:top_k]


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

