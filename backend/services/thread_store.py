"""
Thread Storage
Separate Qdrant collections for chat messages and thread summaries
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from . import config


# Collections
CHAT_MESSAGES_COLLECTION = "chat_messages"
THREAD_SUMMARIES_COLLECTION = "thread_summaries"


def get_client():
    """Get Qdrant client"""
    from .qdrant_store import client
    return client()


def ensure_chat_collections():
    """
    Ensure chat-related collections exist
    
    1. chat_messages - stores individual chat messages
    2. thread_summaries - stores structured thread summaries
    """
    cl = get_client()
    collections = cl.get_collections().collections
    existing = {c.name for c in collections}
    
    # 1. Chat messages collection
    if CHAT_MESSAGES_COLLECTION not in existing:
        print(f"[ThreadStore] Creating collection: {CHAT_MESSAGES_COLLECTION}")
        
        cl.create_collection(
            collection_name=CHAT_MESSAGES_COLLECTION,
            vectors_config=VectorParams(
                size=1,  # Dummy vector
                distance=Distance.COSINE
            )
        )
        
        # Indexes for fast queries
        cl.create_payload_index(
            collection_name=CHAT_MESSAGES_COLLECTION,
            field_name="thread_id",
            field_schema="keyword"
        )
        
        cl.create_payload_index(
            collection_name=CHAT_MESSAGES_COLLECTION,
            field_name="space_id",
            field_schema="keyword"
        )
        
        cl.create_payload_index(
            collection_name=CHAT_MESSAGES_COLLECTION,
            field_name="sender",
            field_schema="keyword"
        )
        
        print(f"[ThreadStore] Collection {CHAT_MESSAGES_COLLECTION} created")
    
    # 2. Thread summaries collection
    if THREAD_SUMMARIES_COLLECTION not in existing:
        print(f"[ThreadStore] Creating collection: {THREAD_SUMMARIES_COLLECTION}")
        
        cl.create_collection(
            collection_name=THREAD_SUMMARIES_COLLECTION,
            vectors_config=VectorParams(
                size=1,
                distance=Distance.COSINE
            )
        )
        
        cl.create_payload_index(
            collection_name=THREAD_SUMMARIES_COLLECTION,
            field_name="thread_id",
            field_schema="keyword"
        )
        
        cl.create_payload_index(
            collection_name=THREAD_SUMMARIES_COLLECTION,
            field_name="space_id",
            field_schema="keyword"
        )
        
        print(f"[ThreadStore] Collection {THREAD_SUMMARIES_COLLECTION} created")


def save_chat_message(
    thread_id: str,
    space_id: str,
    sender: str,
    text: str,
    recipients: Optional[List[str]] = None,
    message_timestamp: Optional[datetime] = None,
    chat_type: str = "user_chat",
    metadata: Optional[Dict] = None
) -> str:
    """
    Save a single chat message to Qdrant
    
    Args:
        thread_id: Unique thread identifier
        space_id: Workspace/space ID
        sender: Message sender
        text: Message content
        recipients: List of recipients (optional for group chats)
        message_timestamp: When message was sent
        chat_type: Type of chat (user_chat, email, telegram, etc.)
        metadata: Additional metadata (reply_to, attachments, etc.)
    
    Returns:
        message_id (UUID)
    """
    ensure_chat_collections()
    cl = get_client()
    
    message_id = str(uuid.uuid4())
    
    if message_timestamp is None:
        message_timestamp = datetime.utcnow()
    
    if recipients is None:
        recipients = []
    
    if metadata is None:
        metadata = {}
    
    payload = {
        "thread_id": thread_id,
        "space_id": space_id,
        "sender": sender,
        "recipients": recipients,
        "text": text,
        "timestamp": message_timestamp.isoformat(),
        "chat_type": chat_type,
        "message_id": message_id,
        **metadata  # reply_to, subject, etc.
    }
    
    cl.upsert(
        collection_name=CHAT_MESSAGES_COLLECTION,
        points=[
            PointStruct(
                id=message_id,
                vector=[0.0],  # Dummy
                payload=payload
            )
        ]
    )
    
    return message_id


def get_thread_messages(
    thread_id: str,
    space_id: str,
    limit: int = 1000,
    offset: int = 0
) -> List[Dict]:
    """
    Retrieve all messages in a thread
    
    Returns messages sorted by timestamp
    """
    ensure_chat_collections()
    cl = get_client()
    
    results = cl.scroll(
        collection_name=CHAT_MESSAGES_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="thread_id", match=MatchValue(value=thread_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False
    )
    
    messages = [r.payload for r in results[0]]
    
    # Sort by timestamp
    messages.sort(key=lambda m: m.get("timestamp", ""))
    
    return messages


def save_thread_summary(
    thread_id: str,
    space_id: str,
    summary: str,
    chat_type: str,
    participants: List[str],
    message_count: int,
    start_date: str,
    end_date: str,
    action_items: Optional[List[Dict]] = None,
    decisions: Optional[List[str]] = None,
    topics: Optional[List[str]] = None,
    metadata: Optional[Dict] = None
) -> str:
    """
    Save structured thread summary
    
    Returns: summary_id
    """
    ensure_chat_collections()
    cl = get_client()
    
    # Check if summary already exists
    existing = get_thread_summary(thread_id, space_id)
    
    if action_items is None:
        action_items = []
    if decisions is None:
        decisions = []
    if topics is None:
        topics = []
    if metadata is None:
        metadata = {}
    
    payload = {
        "thread_id": thread_id,
        "space_id": space_id,
        "chat_type": chat_type,
        "summary": summary,
        "participants": participants,
        "message_count": message_count,
        "start_date": start_date,
        "end_date": end_date,
        "action_items": action_items,
        "decisions": decisions,
        "topics": topics,
        "generated_at": datetime.utcnow().isoformat(),
        "model": config.LLM_MODEL,
        **metadata
    }
    
    if existing:
        # Update existing summary
        print(f"[ThreadStore] Updating summary for thread {thread_id}")
        
        results = cl.scroll(
            collection_name=THREAD_SUMMARIES_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="thread_id", match=MatchValue(value=thread_id)),
                    FieldCondition(key="space_id", match=MatchValue(value=space_id)),
                ]
            ),
            limit=1
        )
        
        if results[0]:
            summary_id = str(results[0][0].id)
            cl.set_payload(
                collection_name=THREAD_SUMMARIES_COLLECTION,
                payload=payload,
                points=[summary_id]
            )
            return summary_id
    
    # Create new summary
    summary_id = str(uuid.uuid4())
    
    cl.upsert(
        collection_name=THREAD_SUMMARIES_COLLECTION,
        points=[
            PointStruct(
                id=summary_id,
                vector=[0.0],
                payload=payload
            )
        ]
    )
    
    print(f"[ThreadStore] Saved summary for thread {thread_id}")
    return summary_id


def get_thread_summary(thread_id: str, space_id: str) -> Optional[Dict]:
    """Get saved thread summary"""
    try:
        ensure_chat_collections()
    except:
        return None
    
    cl = get_client()
    
    results = cl.scroll(
        collection_name=THREAD_SUMMARIES_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="thread_id", match=MatchValue(value=thread_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False
    )
    
    if not results[0]:
        return None
    
    return results[0][0].payload


def list_threads(
    space_id: str,
    chat_type: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """
    List all threads in a space
    
    Returns basic info about each thread
    """
    ensure_chat_collections()
    cl = get_client()
    
    filter_conditions = [
        FieldCondition(key="space_id", match=MatchValue(value=space_id))
    ]
    
    if chat_type:
        filter_conditions.append(
            FieldCondition(key="chat_type", match=MatchValue(value=chat_type))
        )
    
    # Get all summaries for the space
    results = cl.scroll(
        collection_name=THREAD_SUMMARIES_COLLECTION,
        scroll_filter=Filter(must=filter_conditions),
        limit=limit,
        with_payload=True,
        with_vectors=False
    )
    
    threads = []
    for r in results[0]:
        payload = r.payload
        threads.append({
            "thread_id": payload.get("thread_id"),
            "chat_type": payload.get("chat_type"),
            "participants": payload.get("participants", []),
            "message_count": payload.get("message_count", 0),
            "start_date": payload.get("start_date"),
            "end_date": payload.get("end_date"),
            "summary_preview": payload.get("summary", "")[:200] + "...",
            "has_action_items": len(payload.get("action_items", [])) > 0,
            "generated_at": payload.get("generated_at")
        })
    
    return threads


def delete_thread(thread_id: str, space_id: str) -> bool:
    """
    Delete thread messages and summary
    
    Returns: True if deleted
    """
    ensure_chat_collections()
    cl = get_client()
    
    # Delete messages
    msg_results = cl.scroll(
        collection_name=CHAT_MESSAGES_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="thread_id", match=MatchValue(value=thread_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=10000,
        with_vectors=False
    )
    
    if msg_results[0]:
        msg_ids = [str(r.id) for r in msg_results[0]]
        cl.delete(
            collection_name=CHAT_MESSAGES_COLLECTION,
            points_selector=msg_ids
        )
    
    # Delete summary
    sum_results = cl.scroll(
        collection_name=THREAD_SUMMARIES_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="thread_id", match=MatchValue(value=thread_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=1,
        with_vectors=False
    )
    
    if sum_results[0]:
        sum_id = str(sum_results[0][0].id)
        cl.delete(
            collection_name=THREAD_SUMMARIES_COLLECTION,
            points_selector=[sum_id]
        )
    
    print(f"[ThreadStore] Deleted thread {thread_id}")
    return True

