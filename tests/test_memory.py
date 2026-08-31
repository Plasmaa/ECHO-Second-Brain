import pytest
from api.db.models import Fact, Message
from api.llm.schemas import ExtractedFact
from api.memory.writer import save_message, process_and_save_facts
from api.memory.retrieval import get_active_facts, get_recent_messages, search_similar_messages

@pytest.mark.asyncio
async def test_save_and_retrieve_messages(test_db_session):
    msg1 = await save_message(test_db_session, "web", "user", "Hello ECHO")
    msg2 = await save_message(test_db_session, "web", "assistant", "Hello! How can I help you today?")

    recent = await get_recent_messages(test_db_session, limit=5)
    assert len(recent) == 2
    assert recent[0]["role"] == "user"
    assert recent[1]["role"] == "assistant"

@pytest.mark.asyncio
async def test_fact_extraction_and_supersession(test_db_session):
    # 1. First fact: job = TechCorp
    facts1 = [
        ExtractedFact(
            entity="user",
            attribute="employer",
            value="TechCorp",
            contradicts_existing=False
        )
    ]
    saved1 = await process_and_save_facts(test_db_session, facts1)
    assert len(saved1) == 1
    first_fact_id = saved1[0].id

    # Verify active facts
    active = await get_active_facts(test_db_session)
    assert len(active) == 1
    assert active[0]["entity"] == "user"
    assert active[0]["attribute"] == "employer"
    assert active[0]["value"] == "TechCorp"

    # 2. Second fact: user switched jobs to Dhaka Property Services (contradicts old fact)
    facts2 = [
        ExtractedFact(
            entity="user",
            attribute="employer",
            value="Dhaka Property Services",
            contradicts_existing=True,
            supersedes_fact_id=first_fact_id
        )
    ]
    saved2 = await process_and_save_facts(test_db_session, facts2)
    assert len(saved2) == 1
    second_fact_id = saved2[0].id

    # Active facts must only show the new employer
    active_after = await get_active_facts(test_db_session)
    assert len(active_after) == 1
    assert active_after[0]["id"] == second_fact_id
    assert active_after[0]["value"] == "Dhaka Property Services"

    # Verify old fact is marked superseded_by = second_fact_id
    old_fact = await test_db_session.get(Fact, first_fact_id)
    assert old_fact.superseded_by == second_fact_id

@pytest.mark.asyncio
async def test_semantic_message_retrieval(test_db_session):
    # Create synthetic embeddings
    vec_travel = [1.0] * 384 + [0.0] * 384
    vec_food = [0.0] * 384 + [1.0] * 384

    m1 = await save_message(test_db_session, "web", "user", "I love traveling to Tokyo", embedding=vec_travel)
    m2 = await save_message(test_db_session, "web", "user", "Pizza is my favorite food", embedding=vec_food)

    # Search for travel-related
    query_travel = [0.9] * 384 + [0.1] * 384
    results = await search_similar_messages(test_db_session, query_embedding=query_travel, limit=2)
    assert len(results) >= 1
    assert results[0]["id"] == m1.id
