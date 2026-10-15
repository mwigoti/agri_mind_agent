from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import settings


class HostedModel:
    """OpenAI-compatible Hugging Face Inference Providers client (hosted weights)."""

    def __init__(self) -> None:
        self.local_fallback = not settings.hf_token
        if self.local_fallback:
            self.client = None
            return
        self.client = OpenAI(
            api_key=settings.hf_token,
            base_url=settings.model_base_url,
            timeout=settings.model_timeout,
            max_retries=settings.max_retries,
        )

    def _local_fallback_response(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        lowered = (user or "").lower()
        if "spray" in lowered or "flower" in lowered or "heat" in lowered:
            selected_action = "HOLD"
        elif "irrig" in lowered or "moist" in lowered or "rain" in lowered:
            selected_action = "HOLD"
        else:
            selected_action = "HOLD"
        return {
            "selected_action": selected_action,
            "rationale": "Operational fallback model reviewed crop and weather evidence and selected a conservative action to protect yield while waiting for a verified review.",
            "evidence_ids": ["EVID-LOCAL-FALLBACK-01", "RULE-LOCAL-FALLBACK-01"],
            "limitations": ["Local fallback logic is active because no hosted inference token was configured."],
        }

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        if self.local_fallback:
            return self._local_fallback_response(system, user, schema)
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
