# Second Brain — Personal Memory Agent

A companion AI that remembers you across conversations, extracts and organizes facts about your life automatically, and helps you stay organized — accessible via a self-hosted web app and a Telegram bot.

## Core Concept

Most chatbots forget everything between sessions. This system solves that with a dual memory architecture:

1. **Structured facts** (Postgres table) — exact, queryable knowledge: "job = Data Analyst at Dhaka Property Services." Fast, precise, easy to update.
2. **Semantic memory** (pgvector embeddings) — full conversation chunks embedded for fuzzy recall: "what was I stressed about last month" doesn't match on keywords, it matches on meaning.

Every message the user sends triggers **one merged LLM call** that returns both a conversational reply *and* a structured JSON block of new/updated facts. The backend writes that JSON to Postgres automatically — no manual "save this" step. Memory grows in real time.

When a new fact contradicts an old one (e.g. user changes jobs), the old fact is **not deleted** — it's marked `superseded_by` pointing to the new fact. The system keeps full history and can eventually reason about change over time ("you used to work at X, now Y").

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python) | Async, fast to build, one API serves both clients |
| Database | PostgreSQL + `pgvector` extension | One DB for structured facts *and* embeddings — no separate vector service to run/manage |
| LLM | Google Gemini Flash (free tier, AI Studio) | Best free-tier model in 2026, no credit card, huge context window, supports structured JSON output |
| Interfaces | Self-hosted web app + Telegram bot | Both are thin clients hitting the same FastAPI backend |
| Containerization | Docker Compose | Postgres + API + bot, one `docker compose up` |
| Future fallback | Local model via Ollama (e.g. Qwen3.6, gpt-oss-20B) | Add later for offline/no-quota fallback — NOT used for fact extraction (structured-output reliability matters too much for that; keep extraction on Gemini even after adding local fallback for chat) |

## Database Schema

```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        TEXT NOT NULL CHECK (platform IN ('web', 'telegram')),
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    embedding       VECTOR(768),  -- match Gemini embedding model dimension
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE facts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity              TEXT NOT NULL,        -- e.g. "user", "sister", "job"
    attribute           TEXT NOT NULL,        -- e.g. "name", "employer", "goal"
    value               TEXT NOT NULL,
    confidence          REAL DEFAULT 1.0,
    source_message_id   UUID REFERENCES messages(id),
    superseded_by       UUID REFERENCES facts(id),  -- NULL = currently active fact
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast "current facts only" queries
CREATE INDEX idx_facts_active ON facts (entity, attribute) WHERE superseded_by IS NULL;

-- Index for vector similarity search
CREATE INDEX idx_messages_embedding ON messages USING ivfflat (embedding vector_cosine_ops);
```

## The Merged Call (core mechanism)

Every user message triggers a single Gemini call. System prompt instructs the model to return **strict JSON**:

```json
{
  "reply": "conversational response text shown to the user",
  "extracted_facts": [
    {
      "entity": "user",
      "attribute": "employer",
      "value": "Dhaka Property Services",
      "contradicts_existing": false
    }
  ]
}
```

Backend flow per message:
1. Fetch relevant context: recent messages + top-k semantically similar past messages (pgvector) + all *active* facts (`superseded_by IS NULL`)
2. Build prompt: system instructions + context + user message
3. Call Gemini, parse structured JSON response
4. Send `reply` back to user (web/Telegram)
5. Write user message + assistant reply to `messages` (with embeddings, computed via a separate lightweight embedding call or Gemini's embedding endpoint)
6. For each item in `extracted_facts`: if `contradicts_existing`, set old fact's `superseded_by` to new fact's id; insert new fact row

## API Endpoints (FastAPI)

```
POST /chat
  body: { platform, message }
  → runs the merged call flow above, returns { reply }

GET /facts
  → list all active facts (for a "what do you know about me" debug view)

GET /facts/history/{entity}/{attribute}
  → full supersession chain for one attribute (audit trail)

POST /facts/{id}/correct
  → manual override for a wrong fact (edit UI, not part of v1 required flow)

GET /health
  → liveness check
```

## Project Structure

```
second-brain/
├── docker-compose.yml
├── .env.example
├── api/
│   ├── main.py                 # FastAPI app, routes
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models for messages, facts
│   │   └── migrations/         # Alembic migrations
│   ├── llm/
│   │   ├── gemini_client.py    # wraps Gemini API calls
│   │   └── prompts.py          # system prompt + extraction schema
│   ├── memory/
│   │   ├── retrieval.py        # fetch relevant facts + similar messages
│   │   └── writer.py           # write extracted facts, handle supersession
│   └── routes/
│       ├── chat.py
│       └── facts.py
├── telegram_bot/
│   └── bot.py                  # thin client, calls /chat
├── web/
│   └── (React or plain HTML/JS chat UI)
└── README.md
```

## Build Phases

**Phase 1 — Core loop (this is the MVP, build first)**
- Docker Compose: Postgres (with pgvector) + FastAPI container
- DB schema + Alembic migration
- `/chat` endpoint with the merged Gemini call, hardcoded to a single test user
- Verify: send a message with a fact ("my sister's name is Alex"), confirm it lands correctly in `facts`
- Verify: send a contradicting message later, confirm `superseded_by` chain works

**Phase 2 — Interfaces**
- Minimal web chat UI (single page, calls `/chat`)
- Telegram bot wired to the same endpoint

**Phase 3 — Retrieval quality**
- Add pgvector similarity search for semantic recall
- Tune how much context (recent messages + facts + similar past messages) gets fed into each call — this is where "second brain" quality actually lives

**Phase 4 — Organization features**
- Task/reminder extraction as a fact subtype (e.g. `attribute = "reminder"`, with a due-date field)
- Daily/weekly digest generation ("here's what's changed, here's what's pending")

**Phase 5 — Local fallback**
- Add Ollama-backed local model as fallback for the *chat reply* only when Gemini quota is exhausted
- Keep fact extraction on Gemini even in fallback mode (structured-output reliability matters more than uptime for the memory layer)

## Open Design Questions (decide during build, not before)

- **Entity resolution**: how do we know "my sister" and "Alex" refer to the same entity across messages? (v1 answer: keep it simple, let entity be a free-text string, don't over-engineer a graph yet)
- **Fact conflict detection**: does the LLM alone decide `contradicts_existing`, or does the backend also run a cheap similarity check before trusting the model's judgment?
- **Context window budget**: as facts accumulate over months, feeding "all active facts" into every call stops scaling — will need summarization or relevance filtering eventually (not a v1 problem)

## Notes for Building in Antigravity

- Start with Phase 1 only. Get the merged call + schema working end-to-end with curl/Postman before touching any UI.
- Gemini free tier via Google AI Studio — no credit card required, generous daily quota on Flash models.
- Keep the extraction JSON schema strict and validate it on the backend (don't trust the model to always return perfect JSON — have a fallback/retry path for malformed responses).
