from __future__ import annotations

import hmac
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .audit import AuditLog
from .config import settings
from .graph import create_graph, new_state, resume_graph
from .tool_adapter import MCPTools


class AdvisoryRequest(BaseModel):
    plot_id: str = Field(min_length=1, max_length=100)
    thread_id: str | None = None


class DecisionRequest(BaseModel):
    verdict: str
    reason: str | None = None
    decision_id: str | None = None


audit = AuditLog(settings.audit_path)
tools = MCPTools(audit)
graph = None
saver = None
saver_context = None
decision_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global graph, saver, saver_context
    if not settings.demo_mode:
        await tools.discover()
    graph, saver, saver_context = await create_graph(audit, tools)
    yield
    if saver_context is not None:
        await saver_context.__aexit__(None, None, None)


app = FastAPI(title="AgriMind Layer 2", version="0.1.0", lifespan=lifespan)


def require_api(authorization: str | None = Header(default=None)) -> str:
    expected = settings.api_bearer_token
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(401, detail={"error": "unauthenticated"}, headers={"WWW-Authenticate": "Bearer"})
    return "api-client"


def require_reviewer(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, detail={"error": "unauthenticated"}, headers={"WWW-Authenticate": "Bearer"})
    supplied = authorization[7:]
    for item in settings.reviewer_tokens.split(","):
        if ":" not in item:
            continue
        identity, token = item.split(":", 1)
        if hmac.compare_digest(supplied, token) and identity.strip():
            return identity.strip()
    raise HTTPException(401, detail={"error": "unauthenticated"}, headers={"WWW-Authenticate": "Bearer"})


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "mode": "synthetic_demo" if settings.demo_mode else "integrated", "model_configured": bool(settings.hf_token), "mcp_discovered": bool(tools.contracts) if not settings.demo_mode else False}


@app.post("/api/advisories", status_code=202)
async def start_advisory(payload: AdvisoryRequest, _: str = Depends(require_api)) -> dict[str, Any]:
    if graph is None:
        raise HTTPException(503, detail={"error": "workflow_not_ready"})
    state = new_state(payload.plot_id, payload.thread_id)
    config = {"configurable": {"thread_id": state["thread_id"]}}
    try:
        result = await graph.ainvoke(state, config=config)
    except Exception as exc:
        audit.write({"event": "workflow_failure", "execution_id": state["execution_id"], "thread_id": state["thread_id"], "error": type(exc).__name__})
        raise HTTPException(502, detail={"error": "workflow_failed", "thread_id": state["thread_id"]}) from exc
    return {"thread_id": state["thread_id"], "execution_id": state["execution_id"], "status": result.get("status"), "advisory": result.get("advisory_draft"), "review": result.get("review_prompt"), "errors": result.get("errors", [])}


@app.get("/api/advisories/{thread_id}")
async def get_advisory(thread_id: str, _: str = Depends(require_api)) -> dict[str, Any]:
    if graph is None:
        raise HTTPException(503, detail={"error": "workflow_not_ready"})
    state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    values = state.values
    if not values:
        raise HTTPException(404, detail={"error": "not_found"})
    return {key: values.get(key) for key in ("execution_id", "thread_id", "plot_id", "status", "selected_action", "rationale", "evidence_ids", "advisory_draft", "officer_decision", "officer_identity", "decision_timestamp", "simulated_sms", "errors")}


@app.post("/api/advisories/{thread_id}/decide")
async def decide(thread_id: str, payload: DecisionRequest, officer: str = Depends(require_reviewer)) -> dict[str, Any]:
    if graph is None:
        raise HTTPException(503, detail={"error": "workflow_not_ready"})
    verdict = payload.verdict.upper()
    if verdict not in {"APPROVE", "REJECT"}:
        raise HTTPException(422, detail={"error": "invalid_verdict"})
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    values = state.values
    if not values:
        raise HTTPException(404, detail={"error": "not_found"})
    if values.get("status") != "PENDING_APPROVAL" or not state.next:
        raise HTTPException(409, detail={"error": "execution_not_pending"})
    async with decision_lock:
        # Re-read under the process lock so duplicate concurrent decisions are rejected.
        state = await graph.aget_state(config)
        values = state.values
        if values.get("status") != "PENDING_APPROVAL" or not state.next:
            raise HTTPException(409, detail={"error": "execution_not_pending"})
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            result = await resume_graph(graph, thread_id, {"verdict": verdict, "officer_identity": officer, "decision_timestamp": stamp, "reason": payload.reason, "decision_id": payload.decision_id})
        except Exception as exc:
            raise HTTPException(409, detail={"error": "decision_conflict"}) from exc
    return {"thread_id": thread_id, "status": result.get("status"), "decision": verdict, "officer_identity": officer, "decision_timestamp": stamp, "simulated_sms": result.get("simulated_sms")}


@app.get("/api/demo/ranking")
async def demo_ranking(_: str = Depends(require_api)) -> dict[str, Any]:
    if not settings.demo_mode:
        raise HTTPException(404, detail={"error": "demo_unavailable"})
    from .synthetic import ranking
    return {"label": "SYNTHETIC demonstration heuristic; not agronomic advice", "plots": ranking()}
