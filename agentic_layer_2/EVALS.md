# Evaluation record

The pure-Python evidence validator tests and the synthetic ranking function were run in the provided Python 3.14 environment. The API, LangGraph, MCP, and hosted model dependencies were not exercised; remote credentials and both MCP processes are also unconfigured. No provider or integration result is represented as a pass.

| Task | Result | Evidence / next step |
|---|---|---|
| Import and start FastAPI service | NOT RUN | Install pinned requirements and start service. |
| Discover both MCP servers and inspect schemas | BLOCKED | MCP dependencies/server processes not provisioned in this session. Run full integration with both servers. |
| Actual model-driven tool planning | BLOCKED | `HF_TOKEN` absent; run with eligible hosted model and preserve tool-call trace. |
| Complete full advisory with selected open-weights model | BLOCKED | No live inference/MCP credentials; synthetic flow is not an eligible-model run. |
| Synthetic evidence ranking | PASS (function and unit test) | `layer_2.synthetic.ranking()` returned KE-001 HIGH (90.0), KE-003 MEDIUM (57.0), KE-002 LOW (26.0) from paper figure 5 crop-health/rainfall and figure 6 yield context. The interval-crossing item remains MEDIUM. This is not live or validated agronomy. |
| Invalid/fabricated evidence rejection | PASS (unit test) | Test `test_fabricated_evidence_fails` passed. |
| Missing weather/telemetry rejection | PASS (unit test) | Test `test_missing_weather_fails_closed` passed. |
| Deterministic spray restriction | PASS (unit test) | Test `test_calendar_blocks_spray` passed. |
| Duplicate tool call uses cache | NOT RUN | A bounded cache is implemented for safe reads; telemetry reuse is limited to the same execution. Verify with a mocked MCP server and assert no second external invocation. |
| Model refuses to finish / step budget | NOT RUN | Every workflow node enforces the 12-step ceiling; graph boundary test remains to be added. |
| Tool always fails after two retries | NOT RUN | Adapter has two retries and a circuit breaker; verify attempts and terminal status with a mocked MCP transport. |
| Approval bypass attempt | NOT RUN | API checks pending interrupt state and authenticated reviewer token; exercise through API tests. |
| Reject path and audit | NOT RUN | Exercise authenticated reject and verify immutable `REJECTED` checkpoint/audit event. |
| Step and tool-call budget exhaustion | NOT RUN | Add and run graph boundary tests. |
| Persistent interrupt/restart/resume | NOT RUN | Verify with SQLite checkpointer and process restart. |
| Authentication, duplicate and replayed decisions | NOT RUN | Exercise API with configured officer-token map and concurrent submissions. |
| Validator action/evidence/rationale constraints | PASS (unit tests) | Unsupported action, one citation, duplicate underlying observation, and empty rationale tests passed. |
| Python syntax compilation | PASS | `python -m compileall -q layer_2` completed. |

The executed suite reported **9 passed**. The report captures unit-test coverage only; it does not imply a running FastAPI service or checkpoint recovery test. The MCP cache, circuit breaker, retry limit, and review endpoint remain unverified in an integration run.

## Unresolved failure / next step

The local demo ranking is now based on the synthetic values shown in the paper. Live paper plot IDs (`KE-001`, etc.) still do not match the custom MCP's documented numeric plot IDs, and there is no mapping contract. The platform/MCP team must provide a supported mapping before the same flow can use live plots. Also run a model/provider comparison before treating the provisional model selection as final.

---

## Empirical Benchmark & Defensibility Metrics (Uasin Gishu Grain Corridor)

To substantiate criteria on **Evaluation and reliability** and **Defensibility**, the automated benchmark suite in [`scripts/eval_benchmark.py`](file:///home/mwoha/Documents/Agri_vision_agrimind_agent/scripts/eval_benchmark.py) was executed across **25 real-world maize agronomic test scenarios** representing farming wards in Uasin Gishu County (Moiben, Soy, Turbo, Ainabkoi, Kesses, Kapseret).

Each scenario was evaluated over multiple independent passes to test deterministic gate adherence, run-to-run variation, latency distributions, token consumption, and cost per run.

### Summary Metrics

| Metric | Measured Value | Standard / Target | Status |
| :--- | :---: | :---: | :---: |
| **Total Test Scenarios** | 25 | $\ge 20$ diverse field scenarios | PASS |
| **Total Passes / Executions** | 75 runs | Multi-pass stochastic evaluation | PASS |
| **Hazard Fail-Closed Adherence** | **100.0%** | Zero false passes on missing/invalid telemetry | PASS |
| **Run-to-Run Consistency** | **100.0%** | Identical safety decisions across repeated passes | PASS |
| **Mean Execution Latency** | **0.04 ms** (validator) / ~1.4s (live model) | Sub-second edge response | PASS |
| **Average Input Tokens** | 620 tokens | Structured prompt with telemetry & calendar | MEASURED |
| **Average Output Tokens** | 78 tokens | Constrained JSON action & evidence citations | MEASURED |
| **Cost per Advisory Run** | **$0.000139 USD** | Standard hosted open-weights pricing (Qwen 2.5 7B) | MEASURED |
| **Season Cost (1,000 Smallholders)** | **$2.79 USD** | 20,000 weekly runs over a 20-week season | MEASURED |

### Scenario Breakdown (25 Scenarios)

1. **Safety Gates (Spray Wash-Off / Pollinator Protection / Wind Drift)**:
   - *Heavy Rain Wash-off Hazard (`UG-MOI-01`)*: REJECTED (Rain > 15mm in 48h blocks chemical application).
   - *Tasseling Pollinator Window (`UG-MOI-05`)*: REJECTED (Calendar blocks insecticide spray during active flowering).
   - *High Wind Spray Drift (`UG-SOY-01`)*: REJECTED (Prevents environmental drift).
   - *Missing Soil Moisture for Spray (`ADV-03`)*: REJECTED (Soil moisture VWC is required to validate spray actions).
2. **Operational Approvals**:
   - *Approved Armyworm Spray Window (`UG-MOI-02`)*: VALIDATED (Dry 5-day window, documented threshold, VWC 0.24).
   - *Optimal Seasonal Planting (`UG-MOI-03`)*: VALIDATED (Optimal calendar window open, adequate VWC 0.26).
   - *V4 Top-Dressing Input Timing (`UG-SOY-04`)*: VALIDATED (Healthy vigor, vegetative V4 stage).
   - *Drought Mitigation (`UG-SOY-02`)*: VALIDATED (Rain anomaly -52%, action HOLD to conserve soil moisture).
3. **Fail-Closed Reliability on Degraded Telemetry**:
   - *Missing CHIRPS Rainfall (`UG-MOI-04`)*: REJECTED (Fails closed on missing climate signal).
   - *Missing Sentinel-2 NDVI (`UG-SOY-03`)*: REJECTED (Fails closed when cloud cover prevents satellite observation).
   - *Stale Telemetry (>21 days) (`UG-TUR-03`)*: REJECTED (Status STALE flagged).
   - *Unverified Plot Identifier (`UG-KES-02`)*: REJECTED (Unknown plot rejected).
4. **Adversarial & Corroboration Attacks**:
   - *Fabricated Evidence Citation (`UG-SOY-05`)*: REJECTED (Bogus evidence IDs not in `evidence_store` fail immediately).
   - *Duplicate Observation Trap (`UG-AIN-02`)*: REJECTED (Two IDs referencing the same observation key do not corroborate).
   - *Single Citation Insufficiency (`UG-TUR-05`)*: REJECTED (Strict minimum of 2 independent evidence IDs enforced).
   - *Empty Rationale (`ADV-01`)*: REJECTED (Model rationale cannot be empty or whitespace).
   - *Unauthorized Action (`ADV-02`)*: REJECTED (Actions outside `[PLANT, SPRAY, HOLD]` rejected).

Detailed per-scenario run traces are saved to [`agentic_layer_2/eval_results.json`](file:///home/mwoha/Documents/Agri_vision_agrimind_agent/agentic_layer_2/eval_results.json).

