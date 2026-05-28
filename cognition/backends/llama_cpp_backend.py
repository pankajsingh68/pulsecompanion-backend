"""Llama.cpp Backend — future local inference optimization.

Lazy-loads model. Does NOT initialize at import time.
If llama_cpp missing: initialization fails gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LlamaCppConfig:
    model_path: str = ""
    n_ctx: int = 4096
    n_threads: int = 4
    temperature: float = 0.4


class LlamaCppBackend:
    """Llama.cpp local inference backend. Future optimization path.

    Same protocol as Phi3OllamaBackend.
    """

    def __init__(self, config: LlamaCppConfig | None = None) -> None:
        self._config = config or LlamaCppConfig()
        self._model = None
        self._name = "llama_cpp"
        self._available = self._check_availability()

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return self._available

    def _check_availability(self) -> bool:
        """Check if llama_cpp package is importable."""
        try:
            import importlib
            importlib.import_module("llama_cpp")
            return True
        except ImportError:
            logger.info("llama_cpp_not_available")
            return False

    async def complete(
        self, system_prompt: str, user_context: str, max_sentences: int
    ) -> str:
        """Generate completion. Raises if not available."""
        if not self._available:
            raise RuntimeError("llama_cpp_not_installed")
        # Future: lazy-load model and generate
        raise RuntimeError("llama_cpp_not_implemented")

    async def health_check(self) -> bool:
        return self._available
