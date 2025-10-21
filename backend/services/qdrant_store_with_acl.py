"""
Enhanced Qdrant Store with Access Control Integration
Example implementation showing how to integrate access control
"""

import uuid
from typing import List, Optional, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    HnswConfigDiff,
    SearchParams,
)
from . import config
from .config import QDRANT_URL, QDRANT_COLLECTION
from .embeddings import embed, dim
from .access_control import AccessContext, AccessControlService, augment_payload_with_access_control

_client: Optional[QdrantClient] = None


def client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL)
        ensure_collection()
    return _client


def ensure_collection():
    """Create collection with proper indexing for access control fields"""
    c = QdrantClient(url=QDRANT_URL)
    try:
        c.get_collection(QDRANT_COLLECTION)
    except Exception:
        c.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim(), distance=Distance.COSINE),
            hnsw_config=HnswConfigDiff(
                m=config.QDRANT_HNSW_M, 
                ef_construct=config.QDRANT_HNSW_EF_CONSTRUCT
            ),
        )
        
        # Create payload indexes for efficient filtering
        # These indexes dramatically speed up filtered searches
        c.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="space_id",
            field_schema="keyword"
        )
        c.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="channel_id",
            field_schema="keyword"
        )
        c.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="owner_id",
            field_schema="keyword"
        )
        c.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="visibility",
            field_schema="keyword"
        )
        c.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="doc_type",
            field_schema="keyword"
        )
        c.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="department",
            field_schema="keyword"
        )
        c.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="security_level",
            field_schema="integer"
        )


def upsert_chunks_with_acl(
    space_id: str,
    doc_id: str,
    doc_type: str,
    chunks: List[str],
    access_metadata: Dict,  # Contains: owner_id, visibility, agent_roles, etc.
    channel_id: Optional[str] = None,
):
    """
    Upsert chunks with access control metadata
    
    Args:
        space_id: Space/organization ID
        doc_id: Document ID
        doc_type: Document type
        chunks: Text chunks
        access_metadata: Access control metadata from augment_payload_with_access_control
        channel_id: Optional channel ID for channel-scoped documents
    """
    points = []
    for idx, text in enumerate(chunks):
        vec = embed(text)
        payload = {
            "doc_id": doc_id,
            "space_id": space_id,
            "channel_id": channel_id or "",
            "doc_type": doc_type,
            "chunk_index": idx,
            "text": text,
            **access_metadata  # Add access control fields
        }
        points.append(PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload))
    
    if points:
        client().upsert(collection_name=QDRANT_COLLECTION, points=points)


def semantic_search_with_acl(
    q: str,
    access_context: AccessContext,
    doc_types: Optional[List[str]] = None,
    top_k: int = 8
) -> List[Dict]:
    """
    Semantic search with access control
    
    Args:
        q: Query text
        access_context: Access context (user or agent)
        doc_types: Optional document type filter
        top_k: Number of results
        
    Returns:
        List of search results accessible by the context
    """
    qv = embed(q)
    
    # Build filter using access control service
    acl_service = AccessControlService()
    flt = acl_service.build_access_filter(access_context, doc_types)
    
    hits = client().search(
        collection_name=QDRANT_COLLECTION,
        query_vector=qv,
        query_filter=flt,
        limit=top_k,
        search_params=SearchParams(hnsw_ef=config.QDRANT_HNSW_EF_SEARCH),
    )
    
    # Double-check access at result level (defense in depth)
    results = []
    for h in hits:
        if acl_service.can_access_document(access_context, h.payload):
            results.append({
                "key": f"{h.payload.get('doc_id')}:{h.payload.get('chunk_index')}",
                "score": float(h.score),
                "payload": h.payload
            })
    
    return results


def delete_by_doc(doc_id: str, access_context: Optional[AccessContext] = None):
    """
    Delete document with optional access control check
    
    Args:
        doc_id: Document ID to delete
        access_context: If provided, checks if user has permission to delete
    """
    if access_context:
        # First, check if user owns the document or is admin
        # Query document to check ownership
        results = client().scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=1
        )
        
        if results[0]:
            doc_payload = results[0][0].payload
            owner_id = doc_payload.get("owner_id")
            
            # Check if user is owner or admin
            is_owner = access_context.user_id == owner_id
            is_admin = access_context.user_role and access_context.user_role.value == "admin"
            
            if not (is_owner or is_admin):
                raise PermissionError(f"User {access_context.user_id} cannot delete document {doc_id}")
    
    # Perform deletion
    client().delete(
        QDRANT_COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        )
    )


def get_user_documents(user_id: str, space_id: str, limit: int = 100) -> List[Dict]:
    """
    Get all documents owned by a user in a space
    
    Args:
        user_id: User ID
        space_id: Space ID
        limit: Maximum number of documents
        
    Returns:
        List of document payloads
    """
    results = client().scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="owner_id", match=MatchValue(value=user_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=limit
    )
    
    return [point.payload for point in results[0]]


def update_document_access(
    doc_id: str,
    new_access_metadata: Dict,
    access_context: AccessContext
):
    """
    Update access control metadata for a document
    
    Args:
        doc_id: Document ID
        new_access_metadata: New access control fields
        access_context: User context (must be owner or admin)
    """
    # Scroll through all chunks of the document
    results, next_offset = client().scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
        limit=1000
    )
    
    if not results:
        raise ValueError(f"Document {doc_id} not found")
    
    # Check ownership
    owner_id = results[0].payload.get("owner_id")
    is_owner = access_context.user_id == owner_id
    is_admin = access_context.user_role and access_context.user_role.value == "admin"
    
    if not (is_owner or is_admin):
        raise PermissionError(f"User {access_context.user_id} cannot modify document {doc_id}")
    
    # Update all chunks
    for point in results:
        point.payload.update(new_access_metadata)
        client().upsert(
            collection_name=QDRANT_COLLECTION,
            points=[PointStruct(
                id=point.id,
                vector=point.vector,
                payload=point.payload
            )]
        )


# Backward compatibility wrappers (optional)
def upsert_chunks(space_id: str, doc_id: str, doc_type: str, chunks: List[str]):
    """Legacy function without ACL - defaults to public visibility"""
    from .access_control import Visibility, AgentRole
    
    access_metadata = augment_payload_with_access_control(
        base_payload={},
        owner_id="system",
        visibility=Visibility.PUBLIC,
        allowed_agent_roles=[AgentRole.ANALYTICS, AgentRole.RESEARCH, AgentRole.SUPPORT],
    )
    
    upsert_chunks_with_acl(space_id, doc_id, doc_type, chunks, access_metadata)


def semantic_search(
    q: str,
    space_id: Optional[str],
    doc_types: Optional[List[str]],
    top_k: int = 8
):
    """Legacy function without ACL - uses public access context"""
    from .access_control import AccessContext
    
    context = AccessContext(space_id=space_id)
    return semantic_search_with_acl(q, context, doc_types, top_k)

