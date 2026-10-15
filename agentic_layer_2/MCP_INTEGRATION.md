# Layer 2 MCP integration contract

## Required servers

1. `agrimind`: stdio server launched as `python -m mcp_server.server` from repository root.
2. `historical`: documented third-party `mcp-server-sqlite`, pointed at `data/historical_records.db`.

At startup Layer 2 calls `list_tools()` on each and inspects `inputSchema`. Required capabilities currently map to the server README's tool names:

| Workflow capability | Tool | Required inputs used |
|---|---|---|
| plot status | `get_plot_status` | `plot_id: string` |
| telemetry | `analyze_crop_telemetry` | `plot_id: string` |
| deterministic calendar | `evaluate_calendar_window` | `crop`, `phenological_stage`, `rainfall_anomaly_pct`, optional moisture, forecast, plot ID |
| draft persistence | `draft_advisory_for_approval` | `plot_id`, `recommended_action`, `advisory_rationale`, `evidence_ids` |
| historical read | `read_query` | `query: string` (read-only SELECT) |

Layer 2 requires `list_tables`, `describe_table`, and `read_query` only insofar as the borrowed server exposes them; currently it verifies only `read_query`.

## Contract mismatches and assumptions

- The custom server documentation uses numeric or `PLOT-<number>` identifiers. The paper's `KE-001` etc. identifiers are not accepted by its documented plot sanitizer. Upstream must supply a mapping or update its tool contract; the Layer 2 synthetic demo does not solve this for live data.
- The tool documentation's sample telemetry includes soil moisture in one section but not consistently in its schema. Layer 2 omits optional arguments absent from discovered schemas and treats missing critical data as insufficient.
- `draft_advisory_for_approval` deduplicates pending drafts for the plot, but its documented return contract does not expose a caller idempotency key or a reliable lookup operation. Layer 2 deliberately does not retry ambiguous draft writes, but cannot reconcile a timed-out write. Integrators should add an idempotency key or authoritative draft lookup.
- The SQLite MCP server is a separate read-only process. No tested query/plot-ID relationship exists between its sample history and the paper identifiers; historical data is therefore not currently used in recommendations.
- The MCP README describes `HARVEST`; Layer 2 rejects it because the brief permits only PLANT, SPRAY, HOLD.
- The design PDF proposes separate crop-health, rainfall, and yield tools, including `estimate_yield`; the current gateway exposes `analyze_crop_telemetry` with embedded yield prediction and no separate `estimate_yield` capability. Layer 2 uses the current gateway contract and does not recreate the model. Confirm with the platform team whether a separate capability is planned.
- Tool outputs should return structured JSON, status, timestamps/freshness and stable evidence IDs. Stdout must remain MCP protocol-only.
