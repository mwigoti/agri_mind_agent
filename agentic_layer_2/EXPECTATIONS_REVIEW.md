# Review against the supplied AgriMind documents

## Summary

Layer 2 matches the intended architecture and safety boundary in the paper, brief, design diagram, and implementation prompt at the code-design level. The synthetic ranking now uses the values visible in the paper's figures and keeps the interval-crossing KE-003 record at MEDIUM. The service has not completed a live model/MCP/API run, so several operational expectations remain unverified rather than passed.

## Matches

- Preserves the existing platform and uses the MCP boundary; Layer 2 contains no direct platform database access or yield-model rewrite.
- Implements a finite LangGraph with retrieval, action reasoning, deterministic validation, persisted draft, interrupt-based officer decision, and finalization nodes; execution budgets are enforced in code.
- Requires two independent evidence IDs, validates IDs against the execution evidence store, checks current crop-health/rainfall evidence, and requires moisture/calendar permission for PLANT or SPRAY.
- Prevents simulated outbound preparation until an authenticated reviewer resumes a pending graph. Reviewer identity comes from a server-side token map and the service records its own decision timestamp.
- Logs MCP invocations and decisions; adds bounded read caching, retry limits, and a lightweight circuit breaker. The cache does not turn earlier telemetry into evidence for a new execution.
- Reproduces the displayed paper demo inputs: crop-health scores 0.42/0.78/0.61, rainfall anomalies -32%/-4%/-18%, and predicted yields 2.1/4.6/3.4 t/ha for KE-001/KE-002/KE-003. It computes scores without identifier-specific ordering and applies the paper's interval-crossing MEDIUM cap to KE-003.
- Documents the distinction between the self-contained synthetic demo and hosted inference/live MCP integration; does not claim local inference or measured model/yield performance.

## Partial matches or unresolved integration points

- The design PDF sketches separate crop-health, rainfall, and `estimate_yield` tools. The implemented MCP gateway README instead documents `analyze_crop_telemetry`, with yield included in its payload, and no standalone `estimate_yield` tool. Layer 2 follows the actual documented gateway. The gateway team should confirm whether the paper/design diagram needs updating or the tool contract needs an additional capability.
- The borrowed SQLite MCP server is discovered and used for a county-level historical baseline query. It is not used for per-plot history because the numeric history IDs and paper `KE-*` IDs have no documented mapping. Historical context is not treated as current observation evidence.
- The chosen Qwen model and hosted Hugging Face client are configured, but the client currently uses JSON capability planning rather than provider-native function-call envelopes. The specific model/provider has not been run to prove tool choice, argument quality, structured output, cost, or latency. This does not yet satisfy the paper's open-weight model execution claim.
- The evidence validator checks existence, validity, independent observation keys, and broad action gates, but does not fully prove action-specific citation relevance or parse all source freshness/validity metadata from the live server. That needs richer MCP schemas and integration tests.
- Reviewer bearer tokens provide a local demo authentication boundary, not the institutional identity provider/role authorization expected for a deployed extension service.
- SQLite interrupt persistence, restart recovery, concurrent decision behavior, MCP cache behavior, retry/circuit behavior, and the HTTP review API have not been integration-tested.

## Not delivered in this repository

- The paper's eight evaluation scenarios are mapped in `EVALS.md`, but only the unit tests and synthetic ranking have actually run. Full task results remain open.
- The public demo video and public repository URL are not present; the inspected folder has no Git metadata. The approximately 300-word submission description also needs the institution/office name, which was not provided, so it is not invented here.
- Model and yield estimator metrics are absent from the supplied paper and have not been fabricated.

## Verification performed for this review

- `python -m compileall -q layer_2`: passed.
- `python -m pytest -p no:cacheprovider layer_2/tests -q`: 9 passed.
- Synthetic ranking output: KE-001 HIGH (90.0), KE-003 MEDIUM (57.0), KE-002 LOW (26.0).
- Full service, provider, MCP, and checkpoint-resume integration: not run.
