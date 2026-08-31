from __future__ import annotations

import time
from typing import Any

import httpx

from email_assistant.models import LLMImage


class N1NLLMProvider:
    """n1n LLM gateway client using an OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://api.n1n.ai/v1",
        timeout: float = 180.0,
        max_retries: int = 2,
    ) -> None:
        self.model = model
        self._max_retries = max_retries
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "N1NLLMProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def analyze(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        images: list[LLMImage] | None = None,
    ) -> str:
        user_content: str | list[dict[str, Any]]
        if images:
            user_content = [{"type": "text", "text": user_prompt}]
            user_content.extend(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image.data_url,
                    },
                }
                for image in images
            )
        else:
            user_content = user_prompt

        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        response = self._post_with_retries(payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise RuntimeError(f"n1n API request failed: {exc.response.status_code} {detail}") from exc

        data: dict[str, Any] = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected n1n response shape: {data}") from exc

    def _post_with_retries(self, payload: dict[str, Any]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._client.post("/chat/completions", json=payload)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                time.sleep(2**attempt)
        raise RuntimeError("n1n API request timed out after retries.") from last_error
