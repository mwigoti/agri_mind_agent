from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    model_id: str = os.getenv("MODEL_ID", "Qwen/Qwen2.5-7B-Instruct")
    model_provider: str = os.getenv("MODEL_PROVIDER", "auto")
    hf_token: str = os.getenv("HF_TOKEN", "")
    model_base_url: str = os.getenv("MODEL_BASE_URL", "https://router.huggingface.co/v1")
    model_timeout: float = float(os.getenv("MODEL_TIMEOUT", "45"))
    temperature: float = float(os.getenv("MODEL_TEMPERATURE", "0"))
    max_tokens: int = int(os.getenv("MODEL_MAX_TOKENS", "900"))
    max_retries: int = int(os.getenv("MODEL_RETRIES", "2"))
    api_bearer_token: str = os.getenv("API_BEARER_TOKEN", "")
    reviewer_tokens: str = os.getenv("REVIEWER_TOKENS", "")
    checkpoint_path: Path = Path(os.getenv("CHECKPOINT_PATH", "./layer_2/checkpoints.sqlite"))
    audit_path: Path = Path(os.getenv("AUDIT_PATH", "./layer_2/audit.jsonl"))
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    agrimind_command: str = os.getenv("AGRIMIND_MCP_COMMAND", "")
    historical_command: str = os.getenv("HISTORICAL_MCP_COMMAND", "")
    historical_db: Path = Path(os.getenv("HISTORICAL_DB", "./data/historical_records.db"))


settings = Settings()
