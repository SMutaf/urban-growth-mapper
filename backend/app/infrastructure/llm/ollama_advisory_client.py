from typing import Dict, List

import requests

from app.domain.interpretation.advisory_interfaces import AdvisoryLLMUnavailableError

CHAT_PATH = "/api/chat"


class OllamaAdvisoryClient:
    """Real IAdvisoryLLMClient implementation, calling a local (or
    remote - base_url is fully configurable, see app/core/config.py)
    Ollama server's /api/chat endpoint. Low temperature by design (see
    Settings.advisory_llm_temperature, default 0.3) - this is an
    interpretation/comparison task over numbers we already computed, not
    creative writing, and a low temperature measurably reduces the
    model's tendency to invent figures that weren't in the given context.
    """

    def __init__(self, base_url: str, model: str, temperature: float, timeout_seconds: int = 60):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds

    def ask(self, system_prompt: str, conversation: List[Dict[str, str]]) -> str:
        messages = [{"role": "system", "content": system_prompt}, *conversation]
        try:
            response = requests.post(
                f"{self._base_url}{CHAT_PATH}",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": self._temperature},
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            # Connection refused (Ollama not running), DNS failure, timeout,
            # non-2xx status - all real, reportable failures. Never
            # swallowed into an empty/fake reply (see IAdvisoryLLMClient's
            # contract) so the user sees "danışma servisi şu an
            # erişilemiyor", not a suspiciously blank chat response.
            raise AdvisoryLLMUnavailableError(
                f"Ollama sunucusuna ({self._base_url}) ulaşılamadı: {exc}"
            ) from exc

        data = response.json()
        content = data.get("message", {}).get("content")
        if not content:
            raise AdvisoryLLMUnavailableError(
                f"Ollama beklenmeyen bir yanıt döndürdü (message.content boş): {data}"
            )
        return content
