from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    model_id: str = os.getenv("MODEL_ID", "openrouter/free")
    model_provider: str = os.getenv("MODEL_PROVIDER", "auto")
    hf_token: str = os.getenv("HF_TOKEN", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    model_base_url: str = os.getenv("MODEL_BASE_URL", "https://openrouter.ai/api/v1")
    model_timeout: float = float(os.getenv("MODEL_TIMEOUT", "45"))
    temperature: float = float(os.getenv("MODEL_TEMPERATURE", "0"))
    max_tokens: int = int(os.getenv("MODEL_MAX_TOKENS", "900"))
    max_retries: int = int(os.getenv("MODEL_RETRIES", "2"))
    api_bearer_token: str = os.getenv("API_BEARER_TOKEN", "dev-api-token")
    reviewer_tokens: str = os.getenv(
        "REVIEWER_TOKENS",
        "officer:dev-reviewer-token,supervisor:dev-supervisor-token",
    )
    checkpoint_path: Path = Path(os.getenv("CHECKPOINT_PATH", "./agentic_layer_2/checkpoints.sqlite"))
    audit_path: Path = Path(os.getenv("AUDIT_PATH", "./agentic_layer_2/audit.jsonl"))
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    agrimind_command: str = os.getenv("AGRIMIND_MCP_COMMAND", "")
    agrimind_mcp_url: str = os.getenv("AGRIMIND_MCP_URL", "")
    agrimind_mcp_token: str = os.getenv("AGRIMIND_MCP_TOKEN", "")
    historical_command: str = os.getenv("HISTORICAL_MCP_COMMAND", "")
    historical_mcp_enabled: bool = os.getenv("HISTORICAL_MCP_ENABLED", "false").lower() == "true"
    historical_db: Path = Path(os.getenv("HISTORICAL_DB", "./data/historical_records.db"))

    @property
    def model_api_key(self) -> str:
        return self.openrouter_api_key if "openrouter.ai" in self.model_base_url else self.hf_token

    @property
    def model_api_key_name(self) -> str:
        return "OPENROUTER_API_KEY" if "openrouter.ai" in self.model_base_url else "HF_TOKEN"


settings = Settings()
