from layer_2.synthetic import ranking


def test_paper_demo_rank_and_interval_caveat():
    rows = ranking()
    assert [row["plot_id"] for row in rows] == ["KE-001", "KE-003", "KE-002"]
    assert [row["priority"] for row in rows] == ["HIGH", "MEDIUM", "LOW"]
    assert rows[1]["yield_interval_relation"] == "crosses_reference"
