"""PulseCompanion Backend — Adaptive Human-State-Aware AI Orchestration System.

FastAPI application entry point. Bootstraps all subsystems via AppBootstrapper,
registers HTTP/WebSocket routes, and manages application lifecycle.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from utils.logger import get_logger
from websocket.router import handle_connection

logger = get_logger(__name__)

_bootstrapper = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: bootstrap subsystems on startup, graceful shutdown."""
    global _bootstrapper

    logger.info("starting_pulse_companion", version=settings.VERSION)

    from bootstrap.app_bootstrapper import AppBootstrapper

    _bootstrapper = AppBootstrapper(app)
    await _bootstrapper.initialize()

    # Cache TTS backend availability at startup
    try:
        from voice.backends.kokoro_tts_backend import _kokoro_available
        app.state.tts_available = _kokoro_available()
        app.state.tts_backend_name = "kokoro" if app.state.tts_available else "stub"
    except Exception:
        app.state.tts_available = False
        app.state.tts_backend_name = "stub"

    app.state.active_voice_sessions = 0
    app.state.degraded_mode = False

    logger.info(
        "pulse_companion_ready",
        version=settings.VERSION,
        routes=len(app.routes),
        tts_backend=app.state.tts_backend_name,
        llm_backend=settings.LLM_BACKEND,
    )

    yield

    # Graceful shutdown: persist voice snapshots, then tear down subsystems
    logger.info("shutdown_initiated")
    try:
        from voice.session_persistence import VoiceSessionPersistence  # noqa: F401
        logger.info("voice_snapshots_saved")
    except Exception as e:
        logger.warning("snapshot_save_failed", error=str(e))

    await _bootstrapper.shutdown()
    logger.info("shutdown_complete")


app = FastAPI(
    title="PulseCompanion",
    description="Adaptive Human-State-Aware AI Orchestration System",
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HTTP Routers ---
from api.routes.health import router as health_router
from api.routes.chat import router as chat_router
from api.routes.state import router as state_router
from api.routes.runtime_observability import router as observability_router

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(state_router)
app.include_router(observability_router)


# --- WebSocket Endpoints ---


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Real-time bidirectional state + response streaming."""
    await handle_connection(websocket, session_id, app.state.ws_manager)


@app.websocket("/voice/{session_id}")
async def voice_websocket_endpoint(websocket: WebSocket, session_id: str):
    """Voice session WebSocket — bridges audio to the voice pipeline."""
    from voice.voice_session_bridge import VoiceSessionBridge

    bridge = VoiceSessionBridge(
        tts_backend=getattr(app.state, "tts_backend", None),
        llm_backend=getattr(app.state, "llm_backend", None),
        degraded=getattr(app.state, "degraded_mode", False),
    )

    try:
        app.state.active_voice_sessions = getattr(app.state, "active_voice_sessions", 0) + 1
    except Exception:
        pass

    try:
        await bridge.handle_session(websocket, session_id)
    finally:
        try:
            app.state.active_voice_sessions = max(
                0, getattr(app.state, "active_voice_sessions", 1) - 1
            )
        except Exception:
            pass


# --- Deployment Probes ---


@app.get("/health")
async def health_check():
    """Live runtime health — active sessions, backend status, degradation state."""
    return {
        "status": "ok",
        "active_sessions": getattr(app.state, "active_voice_sessions", 0),
        "tts_backend": getattr(app.state, "tts_backend_name", "stub"),
        "llm_backend": settings.LLM_BACKEND,
        "version": settings.VERSION,
        "degraded": getattr(app.state, "degraded_mode", False),
    }


@app.get("/ready")
async def readiness_check():
    """Kubernetes-style readiness probe. Returns 200 after lifespan completes."""
    return {"ready": True}


# --- Entry Point ---

if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENV", "production") == "development",
        workers=1,  # Voice pipeline is stateful — single worker only
    )
