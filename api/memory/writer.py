import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from api.db.models import Message, Fact
from api.llm.schemas import ExtractedFact

logger = logging.getLogger(__name__)

async def save_message(
    session: AsyncSession,
    platform: str,
    role: str,
    content: str,
    embedding: Optional[List[float]] = None
) -> Message:
    """Inserts a new message record."""
    msg = Message(
        id=str(uuid.uuid4()),
        platform=platform,
        role=role,
        content=content,
        embedding=embedding,
        created_at=datetime.now(timezone.utc),
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg

async def update_message_embedding(
    session: AsyncSession,
    message_id: str,
    embedding: List[float]
) -> None:
    """Updates embedding on an existing message."""
    stmt = (
        update(Message)
        .where(Message.id == message_id)
        .values(embedding=embedding)
    )
    await session.execute(stmt)
    await session.commit()

async def process_and_save_facts(
    session: AsyncSession,
    extracted_facts: List[ExtractedFact],
    source_message_id: Optional[str] = None
) -> List[Fact]:
    """
    Processes extracted facts, supersedes outdated records, and persists new active facts.
    """
    saved_facts = []
    now_utc = datetime.now(timezone.utc)

    for item in extracted_facts:
        new_fact_id = str(uuid.uuid4())
        entity_norm = item.entity.strip().lower()
        attribute_norm = item.attribute.strip().lower()
        value_norm = item.value.strip()

        superseded_target_id = item.supersedes_fact_id

        # 1. Check direct supersedes_fact_id if provided by LLM
        if superseded_target_id:
            stmt = select(Fact).where(Fact.id == superseded_target_id, Fact.superseded_by.is_(None))
            res = await session.execute(stmt)
            target = res.scalar_one_or_none()
            if target:
                target.superseded_by = new_fact_id
                target.updated_at = now_utc

        # 2. Fallback: If contradicts_existing is true or matching (entity, attribute) active fact already exists
        if not superseded_target_id or item.contradicts_existing:
            stmt = select(Fact).where(
                Fact.entity == entity_norm,
                Fact.attribute == attribute_norm,
                Fact.superseded_by.is_(None),
                Fact.id != new_fact_id
            )
            res = await session.execute(stmt)
            existing_active_facts = res.scalars().all()
            for old_fact in existing_active_facts:
                if old_fact.value.strip().lower() != value_norm.lower():
                    logger.info(f"Superseding active fact {old_fact.id} ({old_fact.entity}.{old_fact.attribute}='{old_fact.value}') with new fact {new_fact_id} ('{value_norm}')")
                    old_fact.superseded_by = new_fact_id
                    old_fact.updated_at = now_utc

        # 3. Create and add new active fact
        new_fact = Fact(
            id=new_fact_id,
            entity=entity_norm,
            attribute=attribute_norm,
            value=value_norm,
            confidence=1.0,
            source_message_id=source_message_id,
            superseded_by=None,
            created_at=now_utc,
            updated_at=now_utc,
        )
        session.add(new_fact)
        saved_facts.append(new_fact)

    if saved_facts or extracted_facts:
        await session.commit()

    return saved_facts
