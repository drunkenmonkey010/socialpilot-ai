from typing import Any

import httpx

from app.core.config import settings


async def generate_ollama_response(
    prompt: str,
) -> str:
    """Generate a short text response using the configured Ollama model."""

    url = f"{settings.ollama_base_url}/api/generate"

    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 100,
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

    return data["response"].strip()