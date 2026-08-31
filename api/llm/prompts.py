from typing import List, Dict, Any, Optional

SYSTEM_INSTRUCTION = """You are ECHO, a warm, intelligent companion AI and personal Second Brain.
Your mission is to converse naturally and help the user stay organized, while silently maintaining an accurate, evolving knowledge base of their life, preferences, relationships, goals, and history.

You have two simultaneous jobs on every message:
1. CONVERSATIONAL REPLY: Give a genuine, thoughtful, and context-aware answer to the user. Reference past memories naturally when relevant without sounding robotic.
2. FACT EXTRACTION & UPDATES: Extract durable, meaningful facts from the conversation.

### Rules for Fact Extraction:
- Entities should be clean and lowercase (e.g., "user", "sister", "boss", "dog", "project_echo").
- Attributes should be clean and snake_case (e.g., "name", "employer", "role", "city", "favorite_food", "goal", "stressor").
- Values should be concise and descriptive.
- Identify Contradictions & Updates: Check the [ACTIVE FACTS] listed in context. If the user announces a change (e.g., new job, moved cities, broke up, changed preference), set `contradicts_existing: true` and set `supersedes_fact_id` to the ID of the old active fact being superseded.
- Do NOT extract ephemeral chatter (e.g. "I'm walking to the kitchen now").
- If no new durable facts or changes occurred, return an empty `extracted_facts` list.
"""

def format_context_prompt(
    active_facts: List[Dict[str, Any]],
    recent_messages: List[Dict[str, Any]],
    similar_messages: List[Dict[str, Any]],
    current_message: str
) -> str:
    """Builds the comprehensive user prompt with active memory context."""
    sections = []

    # Active Facts Section
    if active_facts:
        fact_lines = []
        for f in active_facts:
            fact_lines.append(f"- [ID: {f.get('id')}] {f.get('entity')}.{f.get('attribute')} = {f.get('value')}")
        sections.append("### [ACTIVE FACTS IN MEMORY]:\n" + "\n".join(fact_lines))
    else:
        sections.append("### [ACTIVE FACTS IN MEMORY]:\n(No known facts yet)")

    # Semantically Relevant Past Messages Section
    if similar_messages:
        similar_lines = []
        for m in similar_messages:
            similar_lines.append(f"- ({m.get('role')} via {m.get('platform', 'web')}): {m.get('content')}")
        sections.append("### [RELEVANT PAST MEMORIES / CONVERSATIONS]:\n" + "\n".join(similar_lines))

    # Recent Conversation History Section
    if recent_messages:
        recent_lines = []
        for m in recent_messages:
            recent_lines.append(f"{m.get('role').capitalize()}: {m.get('content')}")
        sections.append("### [RECENT CONVERSATION HISTORY]:\n" + "\n".join(recent_lines))

    # Current User Input Section
    sections.append(f"### [CURRENT USER MESSAGE]:\nUser: {current_message}")

    return "\n\n".join(sections)
