from __future__ import annotations

import json
from typing import Any

from openai import BadRequestError, OpenAI

from .config import settings


class HostedModel:
    """OpenAI-compatible hosted model client, defaulting to OpenRouter free-only routing."""

    def __init__(self) -> None:
        if not settings.model_api_key and not settings.demo_mode:
            raise RuntimeError(f"{settings.model_api_key_name} is required when DEMO_MODE=false")
        self.local_fallback = not settings.model_api_key
        self.client = OpenAI(
            api_key=settings.model_api_key,
            base_url=settings.model_base_url,
            timeout=settings.model_timeout,
            max_retries=settings.max_retries,
        ) if settings.model_api_key else None

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        if self.local_fallback:
            raise RuntimeError(f"Hosted model is unavailable; configure {settings.model_api_key_name}")
        model = settings.model_id
        if settings.model_provider not in {"", "auto", "huggingface"}:
            model = f"{model}:{settings.model_provider}"
        request = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }
        try:
            response = self.client.chat.completions.create(
                **request,
                response_format={"type": "json_object"},
            )
        except BadRequestError as exc:
            # Inference Providers vary in their support for OpenAI JSON mode.
            # The prompts already request JSON, so retry without the optional
            # response_format constraint when that is the rejected parameter.
            detail = str(exc).lower()
            if "response_format" not in detail and "json mode" not in detail and "json_object" not in detail:
                raise
            response = self.client.chat.completions.create(**request)
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Model response must be a JSON object")
        return result
