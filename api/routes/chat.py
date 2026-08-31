import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.session import get_db, get_session_factory
from api.llm.schemas import ExtractedFact, MergedChatResponse
from api.llm.prompts import format_context_prompt
from api.llm.gemini_client import generate_merged_chat_response, compute_embedding
from api.memory.retrieval import get_active_facts, get_recent_messages, search_similar_messages
from api.memory.writer import save_message, process_and_save_facts, update_message_embedding

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

class ChatRequest(BaseModel):
    platform: str = Field(default="web", description="Platform client ('web' or 'telegram')")
    message: str = Field(..., min_length=1, description="The user's message text")

class ChatResponse(BaseModel):
    reply: str
    extracted_facts: List[ExtractedFact] = Field(default_factory=list)
    user_message_id: str
    assistant_message_id: str

async def _compute_and_save_embeddings(user_msg_id: str, user_content: str, assistant_msg_id: str, assistant_content: str):
    """Background task to compute embeddings without blocking chat response."""
    try:
        user_emb = await compute_embedding(user_content)
        assistant_emb = await compute_embedding(assistant_content)

        session_factory = get_session_factory()
        async with session_factory() as session:
            if user_emb:
                await update_message_embedding(session, user_msg_id, user_emb)
            if assistant_emb:
                await update_message_embedding(session, assistant_msg_id, assistant_emb)
    except Exception as e:
        logger.error(f"Error in background embedding task: {e}")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Core merged conversational endpoint.
    Retrieves context, calls Gemini for reply + structured facts, updates memory, and queues embeddings.
    """
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # 1. Save user message in DB
    user_msg = await save_message(db, platform=req.platform, role="user", content=user_text)

    # 2. Retrieve memory context (active facts, recent history, similar past messages)
    active_facts = await get_active_facts(db)
    recent_messages = await get_recent_messages(db, limit=8)

    # Quick embedding for semantic retrieval if needed
    query_emb = await compute_embedding(user_text)
    similar_messages = []
    if query_emb:
        similar_messages = await search_similar_messages(
            db, query_embedding=query_emb, limit=4, exclude_message_ids=[user_msg.id]
        )

    # 3. Format complete prompt with context
    formatted_prompt = format_context_prompt(
        active_facts=active_facts,
        recent_messages=recent_messages,
        similar_messages=similar_messages,
        current_message=user_text,
    )

    # 4. Single merged LLM call to Gemini
    llm_result: MergedChatResponse = await generate_merged_chat_response(formatted_prompt)

    # 5. Save assistant reply message in DB
    assistant_msg = await save_message(
        db, platform=req.platform, role="assistant", content=llm_result.reply
    )

    # 6. Save extracted facts & apply supersessions
    if llm_result.extracted_facts:
        await process_and_save_facts(
            db, extracted_facts=llm_result.extracted_facts, source_message_id=user_msg.id
        )

    # 7. Queue background task for storing embeddings
    background_tasks.add_task(
        _compute_and_save_embeddings,
        user_msg_id=user_msg.id,
        user_content=user_text,
        assistant_msg_id=assistant_msg.id,
        assistant_content=llm_result.reply,
    )

    return ChatResponse(
        reply=llm_result.reply,
        extracted_facts=llm_result.extracted_facts,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
    )
