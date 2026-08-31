import json
import logging
from typing import List, Optional
from google import genai
from google.genai import types

from api.config import settings
from api.llm.schemas import MergedChatResponse, ExtractedFact
from api.llm.prompts import SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)

# Initialize Google GenAI client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def generate_merged_chat_response(
    formatted_prompt: str,
) -> MergedChatResponse:
    """
    Performs the single merged Gemini call.
    Returns both the conversational reply and structured extracted facts.
    Includes robust fallback parsing if JSON output is wrapped in markdown.
    """
    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=formatted_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=MergedChatResponse,
                temperature=0.7,
            ),
        )

        response_text = response.text.strip() if response.text else "{}"
        
        # Primary: Direct Pydantic validation
        return MergedChatResponse.model_validate_json(response_text)

    except Exception as e:
        logger.warning(f"Direct structured response validation encountered: {e}. Attempting fallback parsing.")
        try:
            # Fallback in case markdown code blocks are present
            cleaned = response.text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            return MergedChatResponse.model_validate(data)
        except Exception as parse_err:
            logger.error(f"Failed to parse Gemini response: {parse_err}. Raw text: {getattr(response, 'text', '')}")
            # Graceful degraded response: return message text as reply with no facts
            reply_text = getattr(response, "text", "") or "I apologize, but I had trouble processing that thought."
            return MergedChatResponse(reply=reply_text, extracted_facts=[])


async def compute_embedding(text: str) -> Optional[List[float]]:
    """
    Generates a 768-dimensional text embedding for semantic search.
    """
    if not text or not text.strip():
        return None

    try:
        result = await client.aio.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.EMBEDDING_DIMENSION
            ),
        )
        if result and result.embeddings and len(result.embeddings) > 0:
            return result.embeddings[0].values
        return None
    except Exception as e:
        logger.error(f"Error computing embedding: {e}")
        return None
