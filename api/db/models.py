import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Conditional Vector type support
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

class VectorType(TypeDecorator):
    """
    Platform-independent vector type.
    Uses pgvector Vector on PostgreSQL, falls back to JSON on SQLite.
    """
    impl = Text
    cache_ok = True

    def __init__(self, dim: int = 768):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform = Column(String(20), nullable=False)  # 'web', 'telegram'
    role = Column(String(20), nullable=False)      # 'user', 'assistant'
    content = Column(Text, nullable=False)
    embedding = Column(VectorType(768), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    facts = relationship("Fact", back_populates="source_message", foreign_keys="Fact.source_message_id")

    __table_args__ = (
        Index("idx_messages_created_at", "created_at"),
    )


class Fact(Base):
    __tablename__ = "facts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity = Column(String(100), nullable=False)     # e.g., "user", "sister", "job"
    attribute = Column(String(100), nullable=False)  # e.g., "employer", "goal", "city"
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    source_message_id = Column(String(36), ForeignKey("messages.id"), nullable=True)
    superseded_by = Column(String(36), ForeignKey("facts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Self-referencing relationships
    source_message = relationship("Message", back_populates="facts", foreign_keys=[source_message_id])
    superseding_fact = relationship("Fact", remote_side=[id], foreign_keys=[superseded_by])

    __table_args__ = (
        Index("idx_facts_active", "entity", "attribute"),
        Index("idx_facts_superseded_by", "superseded_by"),
    )
