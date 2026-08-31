# ECHO — Second Brain & Personal Memory Agent

A companion AI that remembers you across conversations, extracts and organizes facts about your life automatically, and helps you stay organized — accessible via a self-hosted web app and a Telegram bot.

---

## Features

- **Dual-Memory Architecture**:
  - **Structured Facts** (PostgreSQL with supersession history) for exact, queryable knowledge.
  - **Semantic Vector Memory** (`pgvector` HNSW index with 768d embeddings) for associative and contextual recall.
- **Single Merged LLM Call**: Every user message triggers a single Google Gemini Flash call that returns both a conversational response and a structured JSON block of extracted/updated facts.
- **Fact Supersession & Change Audit**: Outdated facts are not deleted — they are linked via `superseded_by` chains to maintain a temporal history of how facts evolve.
- **Asynchronous Embeddings**: Message embeddings are processed in background tasks for sub-second conversational API response times.
- **RESTful API**: Fast and clean endpoints with FastAPI, SQLAlchemy 2.0 Async, and Pydantic.

---

## Tech Stack

| Layer | Choice | Details |
|---|---|---|
| **Backend** | FastAPI (Python 3.12+) | Async REST API, BackgroundTasks |
| **Database** | PostgreSQL 16 + `pgvector` | Dual structured table + HNSW vector indexing |
| **LLM & Embeddings** | Google Gemini 3.6 Flash / Gemini Embedding 001 | Google GenAI SDK with structured Pydantic schemas |
| **Migrations** | Alembic | Versioned schema migrations |
| **Containerization** | Docker Compose | One command PostgreSQL with pgvector container |

---

## Getting Started

### 1. Clone the Repository & Setup Environment

```bash
git clone https://github.com/Plasmaa/ECHO-Second-Brain.git
cd ECHO-Second-Brain

# Create virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your Gemini API Key:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/second_brain
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/second_brain
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_CHAT_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSION=768
```

### 3. Start Database Container (Docker)

```bash
docker compose up -d
```

### 4. Run the API Server

```bash
uvicorn api.main:app --reload --port 8000
```

Access the interactive API docs at `http://localhost:8000/docs`.

---

## API Endpoints

- `POST /chat` — Send message, retrieve context, return conversational reply, extract facts, and queue embeddings.
- `GET /facts` — List all currently active facts.
- `GET /facts/history/{entity}/{attribute}` — Retrieve the full supersession audit trail for an entity attribute.
- `POST /facts/{id}/correct` — Manually correct an active fact.
- `GET /health` — Check service health and configured models.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## License

MIT
