# Layer 2 implementation and review report

## Delivered

- Added a FastAPI review service and finite LangGraph workflow with explicit retrieval, action reasoning, deterministic evidence validation, MCP draft persistence, interrupt-based officer approval, and finalization nodes.
- Added hosted Hugging Face Inference Providers configuration, stdio MCP discovery/schema checks, bounded read-call caching, lightweight per-server circuit breaking, audit JSONL, SQLite checkpoint configuration, server-side reviewer token mapping, and safe simulated-only approval output.
- Added synthetic demo fixtures transcribed from the paper's visible crop-health/rainfall/yield figures, a transparent stress ranking heuristic with the interval-crossing MEDIUM cap, setup material, model comparison, MCP contract, architecture description, and evaluation record.
- Added a root README and MIT license because neither was present in the inspected repository.

## Verification

- `python -m compileall -q layer_2`: PASS.
- `python -m pytest -p no:cacheprovider layer_2/tests -q`: PASS, 9 tests.
- `layer_2.synthetic.ranking()`: PASS for the paper fixture, returning KE-001 HIGH (90.0), KE-003 MEDIUM (57.0), KE-002 LOW (26.0) in descending computed score.
- Full service startup, hosted inference, MCP server discovery/calls, SQLite interrupt recovery, and authenticated API decisions: NOT RUN. Layer 2 runtime dependencies are not present in the environment and remote credentials/services are not configured.

## Acceptance checklist

| Requirement | Status | Evidence / blocker |
|---|---|---|
| Open-weights default and hosted client | BLOCKED | Qwen2.5-7B-Instruct is the provisional Apache-2.0 default; no remote request or model/provider tool-use evaluation was run. |
| Two dynamically discovered MCP servers | BLOCKED | Adapter implemented; no MCP process was launched in verification. |
| Bounded LangGraph and SQLite interrupt | BLOCKED | Workflow/checkpointer code added; runtime compatibility and restart/resume are unverified. |
| Evidence-based recommendation safety | PARTIAL | Deterministic validator tests pass; upstream evidence freshness/semantics and live telemetry remain unverified. |
| Authenticated human approval | PARTIAL | Reviewer identity is mapped server-side from bearer token; API integration/concurrency behavior not runtime-tested. |
| No real outbound action | PASS (code boundary) | Only `SIMULATED_SMS_PREPARED` payload exists; no send client is implemented. |
| Synthetic ranking and KE-003 caveat | PASS (demo only) | Uses the paper's displayed synthetic values and applies the interval-crossing MEDIUM cap. This is not live evidence or a validated agronomic model. |
| Eight evaluation tasks and unresolved issue | PARTIAL | Nine local unit tests pass; full agent task execution remains blocked and is itemized in `EVALS.md`. |
| Public repository and under-three-minute demo video | BLOCKED | Repository is not configured as a Git checkout here; no video hosting or recording was part of the local implementation. |

## Security and remaining work

The local token scheme is demonstration authentication and is not institution-grade identity management. Do not expose the service publicly until it is placed behind institutional authentication, TLS, role authorization, and secret management. Audit redaction covers common contact/name fields but needs production review and retention policy. Upstream uses numeric plot identifiers while the paper uses `KE-*` identifiers; a verified mapping is still needed for live runs. The draft MCP contract also lacks a reliable idempotency lookup for ambiguous write timeouts. See `MCP_INTEGRATION.md` and `EVALS.md` for integration blockers.
