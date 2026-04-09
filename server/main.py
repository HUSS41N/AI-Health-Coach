import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from admin.router import router as admin_router
from chat.router import router as chat_router
from config import get_settings
from database import check_database
from db.session import init_db
from chat.service import shutdown_coach_executor
from prompts.service import seed_prompts_if_needed, warm_agent_prompts
from redis_client import check_redis

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        init_db()
        logger.info("Database tables ensured (create_all)")
    except Exception:
        logger.exception("init_db failed — ensure DATABASE_URL is valid")
    try:
        seed_prompts_if_needed()
        warm_agent_prompts()
    except Exception:
        logger.exception("seed_prompts_if_needed failed")
    yield
    try:
        shutdown_coach_executor()
    except Exception:
        logger.exception("shutdown_coach_executor failed")


settings = get_settings()
allow_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app = FastAPI(
    title="AI Health Coach API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(admin_router)


@app.get("/")
def read_root():
    return {"message": "AI Health Coach API", "docs": "/docs"}


@app.get("/health")
def health():
    db_ok = check_database()
    redis_ok = check_redis()
    overall = "healthy" if db_ok and redis_ok else "degraded"
    return {
        "status": overall,
        "database": {"ok": db_ok},
        "redis": {"ok": redis_ok},
    }
