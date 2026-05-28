"""Phi-3 Ollama Backend — local LLM via Ollama HTTP API.

Uses phi3:mini by default. Never streams. Never logs prompt contents.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Phi3BackendConfig:
    model_name: str = "phi3:mini"
    host: str = "http://localhost:11434"
    timeout_seconds: float = 3.0
    temperature: float = 0.4
    num_ctx: int = 4096


class Phi3OllamaBackend:
    """Phi-3 via Ollama HTTP API. Deterministic generation settings."""

    def __init__(self, config: Phi3BackendConfig | None = None) -> None:
        self._config = config or Phi3BackendConfig()
        self._name = "phi3_ollama"

    @property
    def name(self) -> str:
        return self._name

    async def complete(
        self, system_prompt: str, user_context: str, max_sentences: int
    ) -> str:
        """Generate completion via Ollama. Raises RuntimeError if unavailable."""
        prompt = f"{system_prompt}\n\n{user_context}" if user_context else system_prompt

        # Estimate max tokens from max_sentences (roughly 20 tokens per sentence)
        num_predict = min(max_sentences * 25, 150)

        payload = {
            "model": self._config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self._config.temperature,
                "top_p": 0.8,
                "repeat_penalty": 1.1,
                "num_predict": num_predict,
                "num_ctx": self._config.num_ctx,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                response = await client.post(
                    f"{self._config.host}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                text = result.get("response", "")
                if not text:
                    raise RuntimeError("empty_response_from_ollama")
                # Never log prompt contents
                logger.debug("phi3_completion_success", model=self._config.model_name)
                return text.strip()
        except httpx.TimeoutException:
            raise RuntimeError("ollama_timeout")
        except httpx.ConnectError:
            raise RuntimeError("ollama_unavailable")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"ollama_http_error: {e.response.status_code}")

    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self._config.host}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
