"""Top-level application bootstrapper — called by main.py."""

from __future__ import annotations

from fastapi import FastAPI

from bootstrap.dependency_registry import DependencyRegistry
from bootstrap.observability_bootstrap import bootstrap_observability
from bootstrap.websocket_bootstrap import bootstrap_websocket
from bootstrap.orchestration_bootstrap import bootstrap_orchestration
from bootstrap.streaming_bootstrap import bootstrap_streaming
from bootstrap.runtime_bootstrap import bootstrap_runtime
from utils.logger import get_logger

logger = get_logger(__name__)


class AppBootstrapper:
    """Top-level orchestrator for application initialization.

    Calls each sub-bootstrapper in dependency order and registers
    results into the DependencyRegistry.

    Usage in main.py:
        await AppBootstrapper(app).initialize()
    """

    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self.registry = DependencyRegistry()

    async def initialize(self) -> None:
        """Initialize all subsystems in dependency order."""
        logger.info("bootstrap_starting")

        # 1. Observability (first — others depend on it)
        observability = bootstrap_observability(self.registry)

        # 2. WebSocket infrastructure
        ws_bundle = await bootstrap_websocket(self.registry)

        # 3. Memory manager (best effort)
        self._init_memory()

        # 4. Verify Ollama (non-blocking)
        await self._verify_ollama()

        # 5. Orchestration layer (state engine, confidence, safety, runtime)
        orchestration = bootstrap_orchestration(self.registry, observability)

        # 6. Streaming layer (ingestion, sync, recompute)
        streaming = bootstrap_streaming(
            self.registry, orchestration, ws_bundle.ws_manager, observability
        )

        # 7. Runtime layer (manager, ambient loop, protection, devices)
        runtime = bootstrap_runtime(
            self.registry, orchestration, streaming,
            ws_bundle.ws_manager, observability,
        )

        # 8. Voice backends — registered for injection into voice pipeline
        await self._init_voice_backends()

        # Wire everything into app.state
        self.registry.register_to_app_state(self.app)

        logger.info(
            "bootstrap_complete",
            total_components=self.registry.component_count,
            tts_backend=self.registry.get_optional("tts_backend") is not None,
            llm_backend=self.registry.get_optional("llm_backend") is not None,
            memory_ready=self.registry.get_optional("memory_manager") is not None,
        )

    def _init_memory(self) -> None:
        """Initialize ChromaDB memory manager (best effort)."""
        try:
            from memory.manager import MemoryManager
            mm = MemoryManager()
            self.registry.register("memory_manager", mm)
            logger.info("memory_manager_ready")
        except Exception as e:
            logger.warning("memory_manager_unavailable", error=str(e))
            self.registry.register("memory_manager", None)

    async def _verify_ollama(self) -> None:
        """Verify Ollama connectivity (non-blocking)."""
        try:
            import httpx
            from config import settings
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    logger.info("ollama_connected")
                else:
                    logger.warning("ollama_unhealthy", status=resp.status_code)
        except Exception as e:
            logger.warning("ollama_unavailable", error=str(e))

    async def _init_voice_backends(self) -> None:
        """Initialize and register voice pipeline backends.

        Both registrations are best-effort — None is valid fallback.
        No exception propagates out of this method.
        """
        # TTS backend
        try:
            from voice.backends.kokoro_tts_backend import (
                KokoroTTSBackend, _kokoro_available,
            )
            if _kokoro_available():
                tts = KokoroTTSBackend()
                self.registry.register("tts_backend", tts)
                logger.info("tts_backend_ready", backend="kokoro")
            else:
                self.registry.register("tts_backend", None)
                logger.warning(
                    "tts_backend_unavailable", reason="kokoro_not_installed"
                )
        except Exception as e:
            self.registry.register("tts_backend", None)
            logger.warning("tts_backend_failed", error=str(e))

        # LLM backend
        try:
            from cognition.backends.phi3_ollama_backend import Phi3OllamaBackend
            llm = Phi3OllamaBackend()
            self.registry.register("llm_backend", llm)
            logger.info("llm_backend_ready", backend="phi3_ollama")
        except Exception as e:
            self.registry.register("llm_backend", None)
            logger.warning("llm_backend_failed", error=str(e))

        # Degraded mode flag
        self.registry.register("degraded_mode", False)

    async def shutdown(self) -> None:
        """Graceful shutdown of all subsystems in reverse order."""
        logger.info("bootstrap_shutdown_starting")

        # Stop heartbeat
        heartbeat = self.registry.get_optional("heartbeat")
        if heartbeat:
            try:
                await heartbeat.stop()
            except Exception as e:
                logger.warning("heartbeat_stop_failed", error=str(e))

        # Stop runtime ambient loop if running
        runtime_manager = self.registry.get_optional("runtime_manager")
        if runtime_manager and hasattr(runtime_manager, "stop"):
            try:
                await runtime_manager.stop()
            except Exception as e:
                logger.warning("runtime_stop_failed", error=str(e))

        # Stop streaming layer
        stream_manager = self.registry.get_optional("stream_manager")
        if stream_manager and hasattr(stream_manager, "stop"):
            try:
                await stream_manager.stop()
            except Exception as e:
                logger.warning("stream_stop_failed", error=str(e))

        # Flush memory manager
        memory_manager = self.registry.get_optional("memory_manager")
        if memory_manager and hasattr(memory_manager, "flush"):
            try:
                await memory_manager.flush()
            except Exception as e:
                logger.warning("memory_flush_failed", error=str(e))

        logger.info("bootstrap_shutdown_complete")
