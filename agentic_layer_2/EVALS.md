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
