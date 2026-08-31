from typing import List, Optional
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from api.db.session import get_db
from api.db.models import Fact
from api.memory.retrieval import get_active_facts

router = APIRouter(prefix="/facts", tags=["Facts & Memory"])

class FactItem(BaseModel):
    id: str
    entity: str
    attribute: str
    value: str
    confidence: float
    source_message_id: Optional[str] = None
    superseded_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class CorrectFactRequest(BaseModel):
    value: str = Field(..., min_length=1, description="The corrected value for the fact")
    reason: Optional[str] = Field(default=None, description="Optional note or explanation")

@router.get("", response_model=List[FactItem])
async def list_active_facts(db: AsyncSession = Depends(get_db)):
    """Returns all currently active facts (superseded_by IS NULL)."""
    facts = await get_active_facts(db)
    return [FactItem(**f) for f in facts]

@router.get("/history/{entity}/{attribute}", response_model=List[FactItem])
async def get_fact_history(
    entity: str,
    attribute: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the complete supersession history chain for a specific (entity, attribute).
    Ordered from oldest to newest.
    """
    stmt = (
        select(Fact)
        .where(
            Fact.entity == entity.strip().lower(),
            Fact.attribute == attribute.strip().lower()
        )
        .order_by(Fact.created_at.asc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    if not records:
        raise HTTPException(status_code=404, detail=f"No facts found for {entity}.{attribute}")

    return [
        FactItem(
            id=r.id,
            entity=r.entity,
            attribute=r.attribute,
            value=r.value,
            confidence=r.confidence,
            source_message_id=r.source_message_id,
            superseded_by=r.superseded_by,
            created_at=r.created_at.isoformat() if r.created_at else None,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )
        for r in records
    ]

@router.post("/{fact_id}/correct", response_model=FactItem)
async def correct_fact(
    fact_id: str,
    req: CorrectFactRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually corrects an active fact by marking the old one superseded and creating a new active fact.
    """
    stmt = select(Fact).where(Fact.id == fact_id)
    result = await db.execute(stmt)
    old_fact = result.scalar_one_or_none()
    if not old_fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    new_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)

    # Mark old fact superseded
    old_fact.superseded_by = new_id
    old_fact.updated_at = now_utc

    # Insert corrected fact
    new_fact = Fact(
        id=new_id,
        entity=old_fact.entity,
        attribute=old_fact.attribute,
        value=req.value.strip(),
        confidence=1.0,
        source_message_id=None,
        superseded_by=None,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(new_fact)
    await db.commit()
    await db.refresh(new_fact)

    return FactItem(
        id=new_fact.id,
        entity=new_fact.entity,
        attribute=new_fact.attribute,
        value=new_fact.value,
        confidence=new_fact.confidence,
        source_message_id=new_fact.source_message_id,
        superseded_by=new_fact.superseded_by,
        created_at=new_fact.created_at.isoformat() if new_fact.created_at else None,
        updated_at=new_fact.updated_at.isoformat() if new_fact.updated_at else None,
    )
