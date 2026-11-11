from __future__ import annotations

import pytest
from scripts.eval_benchmark import run_benchmark, SCENARIOS


def test_eval_benchmark_suite_passes():
    """Ensure all 25 Uasin Gishu test scenarios pass with 100% consistency and safety adherence."""
    report = run_benchmark(passes=2)
    assert report["total_scenarios"] == 25
    assert report["accuracy_rate"] == 100.0
    assert report["run_to_run_consistency_pct"] == 100.0
    assert report["safety_gate_fail_closed_rate"] == 100.0
    assert report["cost_per_advisory_run_usd"] > 0.0
    assert report["season_cost_1000_smallholders_usd"] < 5.0  # Under $5 per season for 1,000 farmers

