# Maize Health & Yield Agent Orchestration Setup Guide

## 1. Purpose

This document describes the production-ready agent orchestration layer for the maize health and yield component of AgriVision. It is designed to work with the domain logic defined in [MAIZE_HEALTH_YIELD_README.md](MAIZE_HEALTH_YIELD_README.md) and the MCP tool layer described in [MAIZE_HEALTH_YIELD_MCP_SETUP.md](MAIZE_HEALTH_YIELD_MCP_SETUP.md), while remaining fully independent from Hugging Face integrations.

This is the Phase 2 orchestration layer: it consumes the maize health and yield logic, calls the MCP tools exposed by the Phase 1 integration layer, and then uses a local open-weight model to reason over evidence before a field officer approves or rejects the final agronomic advisory.

The orchestration flow uses:

- LangGraph for stateful, deterministic workflow control
- local open-weight models served through Ollama or vLLM
- MCP tool access to the custom agronomy server and the borrowed Postgres/PostGIS server
- human approval checkpoints for agronomic decisions
- persistent audit logging and safe retry logic for practical deployment

This is the operational layer that turns raw field telemetry, soil context, and historical trends into a safe maize advisory workflow.

---

## 2. Overall architecture

The system is organized into four layers, and the terminology is intentionally aligned with the domain and MCP documents that precede it:

### 2.1 Data and spatial layer

- Postgres/PostGIS database
- historical yield records
- field geometry and season metadata
- soil profiles and weather observations
- maize health snapshots and predictions

### 2.2 MCP layer

- custom FastMCP maize analytics server
- borrowed third-party Postgres/PostGIS MCP server
- tool discovery and schema-based execution

### 2.3 Agent orchestration layer

- LangGraph graph with state management
- local LLM reasoning node
- deterministic validator node
- human approval interrupt node
- final advisory preparation and logging

### 2.4 Human approval and operations layer

- officer approval or rejection interface
- audit logs
- SMS or messaging output preparation
- final execution state persistence

---

## 3. Design goals

The orchestration layer should satisfy the following requirements:

1. Process a field or plot ID and determine which MCP tools to call.
2. Combine structured evidence from the custom agronomy tools and the Postgres/PostGIS read tools.
3. Reason about maize health, moisture stress, yield risk, and operational timing.
4. Route decisions through deterministic guardrails before drafting an advisory.
5. Require human approval for final advisory actions.
6. Keep all runtime logic local and production-friendly without depending on Hugging Face services.

---

## 4. Technology choices

### 4.1 Open-weight model runtime

Use one of the following local model serving paths:

- Ollama: easiest and most operationally simple for local and edge environments
- vLLM: better for higher throughput and scaled deployments
- LM Studio: useful for local desktop experimentation and validation

Do not use Hugging Face hosted inference or Hugging Face Python client code in this orchestration workflow. The model should be served locally from a standard OpenAI-compatible API endpoint or a local Ollama endpoint.

### 4.2 Workflow engine

Use LangGraph with a strict state machine. The system must not be a free-form conversational loop. It should be a bounded action pipeline.

### 4.3 MCP client integration

Use stdio-based MCP client sessions through LangGraph tool adapters. The orchestrator should enumerate tools from both MCP servers and expose them as callable graph tools.

---

## 5. Recommended model stack

A practical production choice is a small-to-medium open-weight instruct model such as:

- Llama 3.1 8B Instruct
- Mistral 7B Instruct
- Qwen 2.5 7B Instruct
- DeepSeek-R1 Distill or a similar open-weight reasoning model if availability is acceptable

For a local hackathon or MVP deployment, a 7B to 8B model is usually sufficient for field advisory reasoning when tool calling is constrained and evidence is structured.

---

## 6. Local setup with Ollama

### 6.1 Install Ollama

For Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Then verify:

```bash
ollama --version
```

### 6.2 Pull a local open-weight model

```bash
ollama pull llama3.1:8b-instruct-q4_0
```

Alternative model examples:

```bash
ollama pull qwen2.5:7b-instruct
ollama pull mistral:7b-instruct
```

### 6.3 Confirm the model is served locally

```bash
ollama run llama3.1:8b-instruct-q4_0
```

The model should be accessible via a local endpoint such as:

```text
http://localhost:11434
```

---

## 7. Python environment

Create a dedicated environment for the orchestration layer:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install langgraph langchain-core langchain-community ollama python-dotenv fastapi uvicorn pydantic mcp httpx redis
```

If using a Postgres-backed state store or audit logging in production, add:

```bash
pip install sqlalchemy psycopg[binary]
```

Do not add Hugging Face-specific dependencies to this orchestration layer unless the project explicitly requires a non-local backend.

---

## 8. Project structure

A clean production structure is:

```text
agri_orchestration/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── state.py
│   ├── tools.py
│   ├── graph.py
│   ├── validators.py
│   ├── prompts.py
│   ├── models.py
│   ├── audit.py
│   └── api.py
├── mcp_clients/
│   ├── maize_mcp_client.py
│   ├── postgis_mcp_client.py
│   └── registry.py
├── services/
│   ├── llm.py
│   ├── cache.py
│   ├── retry.py
│   └── approvals.py
├── .env
├── requirements.txt
├── run_agent.py
└── README.md
```

This separation keeps the workflow maintainable and production-friendly.

---

## 9. Configuration file

Create a `.env` file with local service settings:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_0

AGRI_MCP_SERVER_PATH=python /home/mwoha/Downloads/Agri_vision/maize_health_yield_mcp.py
POSTGIS_MCP_SERVER_COMMAND=docker
POSTGIS_MCP_SERVER_ARGS=run,--rm,-i,--network,host,ghcr.io/modelcontextprotocol/server-postgres,--connection-string,postgresql://agrivision_user:strong_password@localhost:5432/agrivision

MAX_STEPS=12
MAX_TOOL_CALLS=15
WORKER_TIMEOUT_SECONDS=90

APPROVAL_REQUIRED=true
AUDIT_DB_URL=sqlite:///audit.db
LOG_LEVEL=INFO
```

This file keeps the orchestrator portable and allows the model, tool server, and runtime policies to be controlled without code changes.

---

## 10. State schema

The graph must use a strict workflow state rather than an open-ended conversation. This is required by the hackathon guidance and strongly recommended for production use.

```python
from typing import TypedDict, List, Optional, Literal


class AgriState(TypedDict):
    plot_id: str
    evidence_store: List[str]
    advisory_draft: Optional[str]
    officer_decision: Optional[Literal["APPROVE", "REJECT"]]
    step_count: int
    tool_call_count: int
    current_action: Optional[str]
    plan: Optional[str]
    reasoning: Optional[str]
    final_output: Optional[str]
    errors: List[str]
    status: str
```

This state tracks the exact lifecycle needed for maize decision support and review.

---

## 11. Graph workflow

Follow the workflow structure described in the hackathon guide:

### 11.1 plan_and_fetch

The model determines which MCP tools to use based on the plot ID.

Operational responsibilities:

- identify relevant field records
- retrieve soil and crop metadata
- fetch remote-sensing telemetry
- request weather or trend context
- keep evidence IDs and timestamps

### 11.2 reason_action

The model reasons over the returned telemetry and selects one of the core actions:

- PLANT
- SPRAY
- HOLD

For maize health and yield, the decision may also be expressed as:

- IRRIGATE
- ATTEND_TO_PEST_RISK
- HOLD_OPERATION
- INCREASE_MONITORING

### 11.3 deterministic_validator

This is a non-LLM node. It checks all conditions required for a valid recommendation.

For example:

```python
def validate_evidence(evidence_ids: list[str]) -> bool:
    return len(evidence_ids) >= 2
```

If critical environmental variables are missing, route to a fallback state such as INSUFFICIENT_EVIDENCE.

### 11.4 human approval interrupt

When evidence is sufficient, pause the workflow and save the checkpoint before the final advisory is committed.

This is required for agronomic safety and is an important production control.

### 11.5 terminal states

- REJECTED
- SIMULATED_SMS_PREPARED
- INSUFFICIENT_EVIDENCE
- ERROR

---

## 12. Deterministic validator node

The validator should never rely on the model for safety checks. Use pure Python rules.

### 12.1 Example validator

```python
from typing import List


def validate_maize_advisory(evidence_ids: List[str], field_status: dict, telemetry: dict) -> dict:
    errors = []

    if len(evidence_ids) < 2:
        errors.append("At least two evidence items are required before an advisory may be drafted.")

    if not field_status.get("crop_type"):
        errors.append("Crop type is missing.")

    if telemetry.get("overall_health_score") is None:
        errors.append("No maize health score is available.")

    if telemetry.get("water_stress_index") is None:
        errors.append("Water stress cannot be evaluated without moisture data.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }
```

This is the kind of strict guardrail that keeps field recommendations safe and reproducible.

---

## 13. LangGraph workflow skeleton

```python
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver


def plan_and_fetch(state: AgriState):
    # use tool-calling model to decide which MCP functions to call
    return {**state, "status": "FETCHED"}


def reason_action(state: AgriState):
    # analyze returned data and decide PLANT / SPRAY / HOLD
    return {**state, "status": "REASONED"}


def deterministic_validator(state: AgriState):
    # pure Python checks
    return {**state, "status": "VALIDATED"}


def human_approval_interrupt(state: AgriState):
    # pause for officer approval
    return {**state, "status": "AWAITING_APPROVAL"}


def finalize_advisory(state: AgriState):
    return {**state, "status": "SIMULATED_SMS_PREPARED"}


def reject_advisory(state: AgriState):
    return {**state, "status": "REJECTED"}


workflow = StateGraph(AgriState)
workflow.add_node("plan_and_fetch", plan_and_fetch)
workflow.add_node("reason_action", reason_action)
workflow.add_node("deterministic_validator", deterministic_validator)
workflow.add_node("human_approval_interrupt", human_approval_interrupt)
workflow.add_node("finalize_advisory", finalize_advisory)
workflow.add_node("reject_advisory", reject_advisory)

workflow.set_entry_point("plan_and_fetch")
workflow.add_edge("plan_and_fetch", "reason_action")
workflow.add_edge("reason_action", "deterministic_validator")
workflow.add_conditional_edges(
    "deterministic_validator",
    lambda state: "approve" if state["evidence_store"] else "insufficient",
    {
        "approve": "human_approval_interrupt",
        "insufficient": END,
    },
)
workflow.add_conditional_edges(
    "human_approval_interrupt",
    lambda state: "approve" if state["officer_decision"] == "APPROVE" else "reject",
    {
        "approve": "finalize_advisory",
        "reject": "reject_advisory",
    },
)

checkpointer = SqliteSaver.from_conn_string("sqlite:///graph_checkpoints.db")
app = workflow.compile(checkpointer=checkpointer)
```

This is the core pattern that aligns with the hackathon guidance.

---

## 14. Local model integration without Hugging Face

The model layer should be connected through an OpenAI-compatible endpoint or Ollama client.

### 14.1 Ollama Python client example

```python
from ollama import Client

client = Client(host="http://localhost:11434")

response = client.chat(
    model="llama3.1:8b-instruct-q4_0",
    messages=[
        {"role": "system", "content": "You are a maize agronomy advisor. Use only supplied tool evidence and never invent facts."},
        {"role": "user", "content": "Analyze field KE-001 and decide whether to plant, spray, or hold."},
    ],
    tools=[],
    format="json",
)
```

This avoids any dependency on the Hugging Face ecosystem while still allowing a capable local LLM to perform structured reasoning.

---

## 15. MCP client bridge for LangGraph

The orchestration layer should expose both MCP servers as tool sources. Use the standard stdio client bridge pattern.

### 15.1 Example bridge setup

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def load_tools():
    maize_server = StdioServerParameters(
        command="python",
        args=["/home/mwoha/Downloads/Agri_vision/maize_health_yield_mcp.py"],
    )

    postgis_server = StdioServerParameters(
        command="docker",
        args=[
            "run",
            "--rm",
            "-i",
            "--network",
            "host",
            "ghcr.io/modelcontextprotocol/server-postgres",
            "--connection-string",
            "postgresql://agrivision_user:strong_password@localhost:5432/agrivision",
        ],
    )

    async with stdio_client(maize_server) as maize_stdio:
        async with ClientSession(maize_stdio[0], maize_stdio[1]) as maize_session:
            await maize_session.initialize()
            tools = await maize_session.list_tools()
            print(tools)
```

The important principle is that the agent only sees the MCP schema; it does not directly write custom SQL or custom wrappers for trend analysis.

---

## 16. Tool registry pattern

Create a registry that wraps and exposes MCP functions as LangGraph tools.

```python
from langchain_core.tools import tool


@tool
def get_plot_status(plot_id: str):
    """Get field details, crop type, planting date, and growth stage."""
    return call_maize_tool("get_plot_status", {"plot_id": plot_id})


@tool
def analyze_crop_telemetry(plot_id: str):
    """Fetch maize health telemetry and yield estimate."""
    return call_maize_tool("analyze_crop_telemetry", {"plot_id": plot_id})


@tool
def evaluate_calendar_window(crop_stage: str, rain_anomaly: float, spray_risk: bool):
    """Check whether the calendar window supports planting or spraying."""
    return call_maize_tool("evaluate_calendar_window", {
        "crop_stage": crop_stage,
        "rain_anomaly": rain_anomaly,
        "spray_risk": spray_risk,
    })
```

This gives the LLM a narrow, explicit tool surface for maize decision support.

---

## 17. Prompting and system instructions

The model should receive a minimal but highly disciplined system prompt, such as:

```text
You are the AgriVision maize advisory agent.

Rules:
1. Use only tool-provided evidence.
2. Never invent field data, yield values, or weather records.
3. If evidence is missing, respond with INSUFFICIENT_EVIDENCE and do not draft a final recommendation.
4. Prefer deterministic agronomic checks over speculation.
5. Only produce a recommendation after at least two evidence items are available.
6. Safety first: never advise spraying or irrigation without checking weather, moisture, and field conditions.
7. Use structured JSON output with clear action, rationale, and evidence IDs.
```

This prompt keeps the agent honest and aligned with production field safety requirements.

---

## 18. Human approval flow

The human-in-the-loop review is crucial.

### 18.1 Approve/reject API endpoint

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class DecisionPayload(BaseModel):
    officer_name: str
    verdict: str
    timestamp: str
    notes: str | None = None


@app.post("/api/advisories/{thread_id}/decide")
def decide(thread_id: str, payload: DecisionPayload):
    return {"thread_id": thread_id, "status": "received", "verdict": payload.verdict}
```

### 18.2 Behavior

- if officer approves: resume the graph and finalize the advisory
- if officer rejects: route to REJECTED and log the decision
- if evidence is insufficient: route to INSUFFICIENT_EVIDENCE and stop

The approval node should store a clear audit record with officer name, timestamp, and final decision.

---

## 19. Circuit breakers and retry logic

Production deployment requires safe handling of transient failures.

### 19.1 Retry policy

- retry read operations up to 2 times
- short exponential backoff between retries
- if still failing, return a controlled error state

### 19.2 Circuit breaker behavior

If the same MCP tool fails repeatedly, fail fast instead of hammering the service.

Example logic:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout_seconds=60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.open_until = 0

    def allow_request(self):
        return self.failures < self.failure_threshold or time.time() > self.open_until
```

This protects the orchestration workflow during service instability.

---

## 20. Tool call deduplication

The hackathon guidance explicitly recommends caching repeated tool calls to reduce unnecessary queries.

Example:

```python
CACHE = {}


def cached_tool_call(tool_name: str, args: dict):
    key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
    if key in CACHE:
        return CACHE[key]
    result = invoke_tool(tool_name, args)
    CACHE[key] = result
    return result
```

This is particularly useful when the same plot is analyzed repeatedly within a short period.

---

## 21. Audit logging and traceability

Every decision path should leave an audit trail.

Recommended audit fields:

- thread_id
- plot_id
- evidence_ids
- tool names used
- model name and provider
- action selection
- officer name and verdict
- timestamp
- final output

For a production deployment, store audit records in Postgres or SQLite.

---

## 22. Deployment recommendations

### 22.1 Local development

- run Ollama locally
- run the custom maize FastMCP server locally
- run the Postgres/PostGIS MCP server as a Docker container or local process
- run the LangGraph orchestrator locally via Python script or FastAPI service

### 22.2 Production deployment

- host the model behind a local inference service with an OpenAI-compatible API
- keep MCP servers as stable services
- run the orchestrator as a background service or inside a containerized API worker
- persist graph checkpoints and decisions in durable storage
- use structured logging and alerting

---

## 23. Example orchestration flow for a maize plot

### Example input

```json
{
  "plot_id": "KE-001",
  "action": "SPRAY"
}
```

### Example pipeline

1. plan_and_fetch queries the plot status and soil profile
2. analyze_crop_telemetry returns NDVI, water stress, health score, and yield estimate
3. reason_action decides whether to plant, spray, or hold
4. deterministic_validator confirms at least two evidence IDs exist and all required values are present
5. checkpoint is saved and human approval is requested
6. officer approves
7. final advisory is generated and SMS payload is prepared

---

## 24. Safety requirements for maize decisions

This is especially important for maize because environmental conditions change rapidly and the crop is highly sensitive to stress during flowering and grain filling.

The system must always require:

- current field status
- evidence from at least two sources
- valid crop stage context
- weather or stress metrics
- a deterministic safety check before empowering operational advice

---

## 25. Practical production checklist

Before going live, confirm the following:

- local open-weight model is running and reachable
- MCP servers are healthy and discoverable
- tool schemas are loaded at startup
- graph checkpoints are persisted
- approval endpoint is wired to resume workflow control
- logs capture tool calls and evidence IDs
- cache and retry logic are active
- the deterministic validation node blocks unsafe decisions
- the final output is structured and auditable

---

## 26. Minimum implementation stack

For a lean but production-ready deployment, the minimum components are:

- LangGraph
- Python 3.10+
- Ollama or local vLLM server
- custom FastMCP maize server
- Postgres/PostGIS MCP server
- SQLite or Postgres for auditing and checkpoints
- FastAPI for approval endpoint
- Python dotenv for configuration

This is enough to run a stable local orchestration workflow without relying on Hugging Face services.

---

## 27. Final summary

The maize health and yield agent orchestration layer should be built as a bounded, stateful LangGraph workflow that connects to two MCP servers:

- the custom maize agronomy server for field telemetry, crop analysis, and advisory drafting
- the borrowed Postgres/PostGIS MCP server for historic and spatial data access

The LLM used by the agent should be a local open-weight model served through Ollama or vLLM, with no Hugging Face dependency. The workflow must include deterministic validation, explicit human approval states, evidence tracking, retry logic, and checkpoint persistence so that the system is safe, traceable, and production ready.

This architecture satisfies the hackathon guidance while remaining practical for a real-world agricultural decision-support system.
