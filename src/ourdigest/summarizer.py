"""LLM summarizer. Talks to any OpenAI-compatible /chat/completions endpoint."""
from __future__ import annotations

import os
from typing import Iterable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import Story


SYSTEM_PROMPT = (
    "You summarize tech/AI news items for a personal digest. "
    "Given a title and a short snippet, write 1-2 sentences (max 60 words) that "
    "explain what's actually new or interesting. Be factual; don't editorialize. "
    "Don't begin with 'This article' or similar. Output ONLY the summary, no preamble."
)


class Summarizer:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "qwen2.5-7b-instruct",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.timeout = timeout
        if not self.base_url:
            raise ValueError(
                "Summarizer needs OPENAI_BASE_URL (or base_url=) — "
                "point it at your local LLM gateway or hosted API."
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def summarize(self, client: httpx.AsyncClient, story: Story, *, max_chars: int = 1500) -> str:
        user_msg = f"Title: {story.title}\nSource: {story.source}\n\nSnippet:\n{(story.snippet or '')[:max_chars]}"
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 200,
            "temperature": 0.3,
        }
        resp = await client.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()

    async def summarize_many(
        self, client: httpx.AsyncClient, stories: Iterable[Story], *, max_chars: int = 1500
    ) -> None:
        """In-place: fills `story.summary`. Failures leave summary empty (best-effort)."""
        for s in stories:
            try:
                s.summary = await self.summarize(client, s, max_chars=max_chars)
            except Exception:  # noqa: BLE001 — best-effort, never break the pipeline
                s.summary = ""
