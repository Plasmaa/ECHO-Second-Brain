import pytest
from api.llm.gemini_client import generate_merged_chat_response
from api.llm.prompts import format_context_prompt

@pytest.mark.asyncio
async def test_live_gemini_merged_call():
    """Verify live Gemini API produces valid structured responses with extracted facts."""
    active_facts = [
        {"id": "fact-123", "entity": "user", "attribute": "favorite_food", "value": "Sushi"}
    ]
    prompt = format_context_prompt(
        active_facts=active_facts,
        recent_messages=[],
        similar_messages=[],
        current_message="I actually don't like Sushi anymore, now I love Tacos!"
    )
    result = await generate_merged_chat_response(prompt)
    assert result.reply is not None and len(result.reply) > 0
    print("\n[Live Gemini Reply]:", result.reply)
    print("[Extracted Facts]:", result.extracted_facts)

    # Check that Gemini extracted the fact update
    assert len(result.extracted_facts) > 0
    taco_fact = next((f for f in result.extracted_facts if "taco" in f.value.lower()), None)
    assert taco_fact is not None, "Expected Taco fact to be extracted"
