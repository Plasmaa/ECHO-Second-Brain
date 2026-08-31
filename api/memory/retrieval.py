import math
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from api.db.models import Fact, Message

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Fallback cosine similarity computation for non-pgvector environments."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)

async def get_active_facts(session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Fetches all currently active facts (superseded_by IS NULL).
    """
    stmt = (
        select(Fact)
        .where(Fact.superseded_by.is_(None))
        .order_by(Fact.entity.asc(), Fact.attribute.asc())
    )
    result = await session.execute(stmt)
    facts = result.scalars().all()
    return [
        {
            "id": f.id,
            "entity": f.entity,
            "attribute": f.attribute,
            "value": f.value,
            "confidence": f.confidence,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        }
        for f in facts
    ]

async def get_recent_messages(session: AsyncSession, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Fetches the most recent conversation messages in chronological order.
    """
    stmt = (
        select(Message)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()
    # Reverse to return chronological order (oldest to newest)
    messages_chronological = list(reversed(messages))
    return [
        {
            "id": m.id,
            "platform": m.platform,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages_chronological
    ]

async def search_similar_messages(
    session: AsyncSession,
    query_embedding: Optional[List[float]],
    limit: int = 4,
    exclude_message_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Performs semantic vector search over past messages.
    Uses pgvector cosine distance when available, or Python cosine similarity fallback.
    """
    if not query_embedding:
        return []

    bind = session.bind or session.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"

    # PostgreSQL with pgvector optimization
    if dialect_name == "postgresql" and Vector is not None:
        try:
            stmt = select(Message).where(Message.embedding.is_not(None))
            if exclude_message_ids:
                stmt = stmt.where(Message.id.not_in(exclude_message_ids))
            stmt = stmt.order_by(Message.embedding.cosine_distance(query_embedding)).limit(limit)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "platform": m.platform,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ]
        except Exception:
            pass

    # Generic Fallback (e.g. SQLite / In-Memory)
    stmt = select(Message).where(Message.embedding.is_not(None))
    if exclude_message_ids:
        stmt = stmt.where(Message.id.not_in(exclude_message_ids))
    result = await session.execute(stmt)
    all_messages = result.scalars().all()

    scored = []
    for m in all_messages:
        emb = m.embedding
        if isinstance(emb, list):
            score = _cosine_similarity(query_embedding, emb)
            if score > 0.3:  # minimum relevance cutoff
                scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_matches = [m for _, m in scored[:limit]]

    return [
        {
            "id": m.id,
            "platform": m.platform,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in top_matches
    ]
