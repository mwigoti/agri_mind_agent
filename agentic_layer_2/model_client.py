from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import settings


class HostedModel:
    """OpenAI-compatible Hugging Face Inference Providers client (hosted weights)."""

    def __init__(self) -> None:
        if not settings.hf_token:
            raise RuntimeError("HF_TOKEN is required when DEMO_MODE=false")
        self.client = OpenAI(
            api_key=settings.hf_token,
            base_url=settings.model_base_url,
            timeout=settings.model_timeout,
            max_retries=settings.max_retries,
        )

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        model = settings.model_id
        if settings.model_provider not in {"", "auto", "huggingface"}:
            model = f"{model}:{settings.model_provider}"
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Model response must be a JSON object")
        return result
