# Architecture and integration boundary

## Ownership

- **Layer 2 in this folder:** LangGraph state machine, model adapter, MCP client/discovery adapter, evidence checks, SQLite workflow checkpoints, audit log, and authenticated review API.
- **Custom MCP gateway supplied by the team:** `../mcp_server`; Layer 2 calls its `get_plot_status`, `analyze_crop_telemetry`, `evaluate_calendar_window`, and `draft_advisory_for_approval` tools. It remains responsible for upstream data and authoritative draft persistence.
- **Borrowed MCP component:** the documented `mcp-server-sqlite` package, used read-only for historical records. Reuse avoids duplicating a maintained MCP server; the SQLite integration is specified in `../mcp_server/README.md`.
- **AgriVision:** owns authoritative Django/PostGIS records and its yield model. Layer 2 does not access its database directly or reimplement its model.

## Workflow

The finite graph has `plan_and_fetch → reason_action → validate_evidence → draft_call → human_approval → finalize_decision`. Retrieval, reasoning, and validation failures terminate before a draft. The graph limits itself to 12 node executions and 15 MCP invocations, including failed attempts and retries. A bounded five-minute cache deduplicates read-only MCP calls; telemetry is reusable only within the same execution, while historical query results remain historical context. Cache hits are logged and do not count as external calls. Read calls get at most two retries; the mutating draft call is not retried after an ambiguous outcome. A lightweight per-server circuit opens after repeated failures and resets after a short cooldown. Tool calls are discovered over MCP stdio and checked against the returned JSON schema before invocation. MCP payloads are treated as untrusted data.

Evidence comes from returned telemetry IDs and deterministic calendar rule citations. Validation checks current status, telemetry availability, action limits, evidence existence, validity, and distinct observation keys. The service will not draft if validation fails. Model outputs are JSON parsed, constrained to the permitted action set, and cannot modify authoritative records directly. The hosted model recommends; rules and human review control the path.

The `human_approval` node uses LangGraph `interrupt()` and a SQLite checkpointer. Review identity comes from a server-side bearer-token mapping. The server stamps decisions; approval only yields `SIMULATED_SMS_PREPARED`. There is no real messaging capability.

## Model selection (provisional)

| Candidate | Weights/licence | Hosted/provider evidence | Fit and limits |
|---|---|---|---|
| `Qwen/Qwen2.5-7B-Instruct` (default) | Hub model card lists Apache-2.0 | Hub Inference Providers chat-completion interface supports function calling at the API level; actual model/provider pairing still must be exercised | Chosen for Qwen alignment and moderate size. This implementation uses bounded JSON planning/reasoning, not native tool-call envelopes. No AgriMind evaluation or price/latency measurements have been run. |
| `Qwen/Qwen3-4B-Instruct-2507` | Apache-2.0 | Listed in Hub Inference Providers | Smaller alternative; verify specific provider availability and structured output before substituting. |
| `meta-llama/Llama-3.1-8B-Instruct` | Llama 3.1 Community License, not OSI-approved | Hosted availability is provider-dependent | Open weights, but custom license obligations and access conditions make distribution/use less straightforward than Apache-2.0 Qwen. |

The choice is provisional, not a completed model evaluation. HF Inference Providers is hosted inference: the weights remain open-weights but prompts and synthetic records are transmitted through hosted infrastructure. The API provides routed billing and its free credits/pricing can change. Model-specific provider price, rate limits, latency, context behavior, and tool selection have not been verified by a live request. The implementation does not claim to meet the eligible-model task until that run is recorded.

## State and limits

The typed state is in `state.py`. A graph step is one node invocation. An MCP call is one attempted external `call_tool`; retries count toward the 15-call execution budget. Historical cache results are labeled historical context and are not added to the current evidence store. Soil moisture is required to validate planting and spraying; missing moisture cannot authorize either action. HOLD can use available current crop-health and rainfall evidence when another operation's required inputs are unavailable.

## Security / data boundary

The local bearer-token scheme is a demo control. Deploy only behind institutional authentication, TLS, role authorization, and secret management. Do not put real household data or farmer contact details in prompts, logs, or test fixtures. Common contact/name fields are redacted in audit records, but production deployment still needs field-level review and retention controls.
