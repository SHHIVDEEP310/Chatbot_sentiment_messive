import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, engine
from app.ml_service import ModelNotLoadedError, SentimentService
from app.routers import auth, chats, mcp, predict, user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentiment_app")

settings = get_settings()

# Create tables if they don't exist yet. For anything beyond local/dev use,
# swap this for a proper migration tool (e.g. Alembic).
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup: load the model exactly once ---
    # If something already injected a service (e.g. the test suite
    # swapping in a fake), respect it instead of loading the real model.
    if getattr(app.state, "ml_service", None) is None:
        ml_service = SentimentService(model_path=settings.MODEL_PATH)
        try:
            ml_service.load()
        except Exception as exc:  # noqa: BLE001 - deliberately broad
            # Don't crash the whole app if the model isn't in place yet,
            # or ML deps aren't installed, or the checkpoint is malformed —
            # log loudly and let /api/predict return a clear 503 instead.
            logger.error("Model failed to load: %s", exc)
        app.state.ml_service = ml_service

    yield
    # --- Shutdown: nothing to clean up explicitly; process exit handles it ---


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(predict.router)
app.include_router(chats.router)
app.include_router(user.router)
app.include_router(mcp.router)


@app.get("/")
def root():
    return {
        "service": settings.APP_NAME,
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health():
    ml_service = getattr(app.state, "ml_service", None)
    return {
        "status": "ok",
        "model_loaded": bool(ml_service and ml_service.is_ready()),
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )
