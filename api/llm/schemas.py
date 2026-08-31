from pydantic import BaseModel, Field
from typing import List, Optional

class ExtractedFact(BaseModel):
    entity: str = Field(
        description="The subject or entity this fact is about, in lowercase e.g., 'user', 'sister', 'job', 'project', 'mother'"
    )
    attribute: str = Field(
        description="The property or attribute name in snake_case e.g., 'employer', 'name', 'city', 'hobby', 'goal', 'pet'"
    )
    value: str = Field(
        description="The value or statement of the fact e.g., 'Dhaka Property Services', 'Alex', 'Golden Retriever named Max'"
    )
    contradicts_existing: bool = Field(
        default=False,
        description="True if this fact updates, replaces, or contradicts an existing active fact in memory"
    )
    supersedes_fact_id: Optional[str] = Field(
        default=None,
        description="The UUID of the existing active fact that is being superseded/replaced, if applicable"
    )

class MergedChatResponse(BaseModel):
    reply: str = Field(
        description="The conversational, natural reply to send back to the user"
    )
    extracted_facts: List[ExtractedFact] = Field(
        default_factory=list,
        description="List of newly discovered, updated, or reaffirmed facts about the user and their life extracted from the message"
    )
