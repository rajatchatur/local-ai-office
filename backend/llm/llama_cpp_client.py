import asyncio
from typing import Optional

import httpx


class LlamaCppClient:
    """
    Async client for the local oMLX OpenAI-compatible API.

    oMLX server:
        http://127.0.0.1:8000

    Default model:
        qwen3-1.7b

    The class name is intentionally kept as LlamaCppClient
    so the existing BossAgent architecture does not need to change.
    """

    def __init__(
        self,
        model: str = "qwen3-1.7b",
        base_url: str = "http://127.0.0.1:8000",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

        # Serialize requests because the Mac has limited RAM.
        self._semaphore = asyncio.Semaphore(1)

        self.timeout = httpx.Timeout(
            connect=10.0,
            read=300.0,
            write=30.0,
            pool=300.0,
        )

    async def generate(
    self,
    prompt: str,
    system: Optional[str] = None,
    format: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 300,
) -> str:

        messages = []

        if system:
            messages.append(
                {
                    "role": "system",
                    "content": system,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "max_tokens": max_tokens,
                "chat_template_kwargs": {
                    "enable_thinking": False
                },
            }

        if temperature is not None:
            payload["temperature"] = temperature

        if format == "json":
            payload["response_format"] = {
                "type": "json_object"
            }

        async with self._semaphore:

            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )

                response.raise_for_status()

                data = response.json()

                choices = data.get("choices", [])

                if not choices:
                    return ""

                message = choices[0].get("message", {})

                return message.get("content", "")
