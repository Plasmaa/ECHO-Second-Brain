import pytest
from unittest.mock import patch, AsyncMock
from api.llm.schemas import MergedChatResponse, ExtractedFact

@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    response = await test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "echo-second-brain"

@pytest.mark.asyncio
async def test_chat_and_facts_lifecycle(test_client):
    # Mock Gemini call to ensure deterministic test without consuming API quota in unit tests
    mock_llm_response = MergedChatResponse(
        reply="Congratulations on your new role as Data Analyst at Dhaka Property Services!",
        extracted_facts=[
            ExtractedFact(
                entity="user",
                attribute="employer",
                value="Dhaka Property Services",
                contradicts_existing=False
            ),
            ExtractedFact(
                entity="user",
                attribute="role",
                value="Data Analyst",
                contradicts_existing=False
            )
        ]
    )

    with patch("api.routes.chat.generate_merged_chat_response", new=AsyncMock(return_value=mock_llm_response)), \
         patch("api.routes.chat.compute_embedding", new=AsyncMock(return_value=[0.1] * 768)):

        # 1. Send chat message
        payload = {
            "platform": "web",
            "message": "I got hired as a Data Analyst at Dhaka Property Services today!"
        }
        res = await test_client.post("/chat", json=payload)
        assert res.status_code == 200
        res_data = res.json()
        assert "Dhaka Property Services" in res_data["reply"]
        assert len(res_data["extracted_facts"]) == 2

        # 2. Check /facts endpoint
        facts_res = await test_client.get("/facts")
        assert facts_res.status_code == 200
        facts_list = facts_res.json()
        assert len(facts_list) == 2
        employer_fact = next(f for f in facts_list if f["attribute"] == "employer")
        assert employer_fact["value"] == "Dhaka Property Services"

        # 3. Check /facts/history/user/employer
        history_res = await test_client.get("/facts/history/user/employer")
        assert history_res.status_code == 200
        history_list = history_res.json()
        assert len(history_list) == 1

        # 4. Correct a fact manually via /facts/{id}/correct
        fact_id_to_correct = employer_fact["id"]
        correct_res = await test_client.post(
            f"/facts/{fact_id_to_correct}/correct",
            json={"value": "Dhaka Property Services Ltd."}
        )
        assert correct_res.status_code == 200
        corrected_fact = correct_res.json()
        assert corrected_fact["value"] == "Dhaka Property Services Ltd."
        assert corrected_fact["superseded_by"] is None

        # Verify active facts has the updated one
        facts_after = (await test_client.get("/facts")).json()
        active_employer = next(f for f in facts_after if f["attribute"] == "employer")
        assert active_employer["value"] == "Dhaka Property Services Ltd."

        # Verify history has 2 records in the chain
        history_after = (await test_client.get("/facts/history/user/employer")).json()
        assert len(history_after) == 2
        assert history_after[0]["superseded_by"] == corrected_fact["id"]
