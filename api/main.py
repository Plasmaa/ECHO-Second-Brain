import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.db.session import init_db
from api.routes.chat import router as chat_router
from api.routes.facts import router as facts_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("echo")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ECHO Second Brain Database...")
    try:
        await init_db()
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
    yield
    logger.info("ECHO Second Brain shutting down.")

app = FastAPI(
    title="ECHO — Second Brain & Personal Memory Agent",
    description="Dual memory companion AI with structured facts supersession & semantic pgvector recall.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup for Web UI and third-party clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routes
app.include_router(chat_router)
app.include_router(facts_router)

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": "echo-second-brain",
        "chat_model": settings.GEMINI_CHAT_MODEL,
        "embedding_model": settings.GEMINI_EMBEDDING_MODEL,
        "embedding_dimension": settings.EMBEDDING_DIMENSION,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
