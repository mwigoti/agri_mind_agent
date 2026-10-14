from __future__ import annotations

from typing import Any, Literal, TypedDict


Action = Literal["PLANT", "SPRAY", "HOLD"]
Status = Literal[
    "RUNNING", "PENDING_APPROVAL", "COMPLETED", "REJECTED", "FAILED",
    "MAX_STEPS_EXCEEDED", "MAX_TOOL_CALLS_EXCEEDED", "INSUFFICIENT_EVIDENCE",
    "SIMULATED_SMS_PREPARED",
]


class Evidence(TypedDict, total=False):
    evidence_id: str
    source: str
    type: str
    value: Any
    retrieved_at: str
    units: str | None
    valid: bool
    observation_key: str


class AgriState(TypedDict, total=False):
    execution_id: str
    thread_id: str
    plot_id: str
    evidence_store: dict[str, Evidence]
    evidence_ids: list[str]
    selected_action: Action | None
    rationale: str
    advisory_draft: dict[str, Any] | None
    step_count: int
    tool_call_count: int
    officer_decision: str | None
    officer_identity: str | None
    decision_timestamp: str | None
    status: Status
    errors: list[str]
    audit_metadata: dict[str, Any]
    plot_status: dict[str, Any]
    telemetry: dict[str, Any]
    calendar: dict[str, Any]
    validation: dict[str, Any]
    review_prompt: dict[str, Any]
    simulated_sms: dict[str, Any] | None
    history: dict[str, Any] | None


MAX_STEPS = 12
MAX_TOOL_CALLS = 15
