from layer_2.validators import validate


def valid_state():
    store = {
        "EVID-A": {"valid": True, "observation_key": "sentinel:ndvi:1"},
        "EVID-B": {"valid": True, "observation_key": "chirps:rain:1"},
    }
    return {
        "plot_status": {"status": "OK"},
        "telemetry": {"status": "OK", "telemetry": {"vegetation_indices": {"ndvi_latest": 0.5}, "water_and_climate": {"rainfall_anomaly_pct": -5, "soil_moisture_vwc": 0.22}}},
        "calendar": {"status": "OK", "operational_windows": {"spraying_permitted": True, "planting_permitted": True}},
        "selected_action": "HOLD", "rationale": "Review measured stress and stage.",
        "evidence_store": store, "evidence_ids": list(store),
    }


def test_valid_evidence_and_action_pass():
    assert validate(valid_state()) == (True, [])


def test_fabricated_evidence_fails():
    state = valid_state()
    state["evidence_ids"] = ["EVID-A", "EVID-FAKE"]
    ok, errors = validate(state)
    assert not ok
    assert any("absent or invalid" in item for item in errors)


def test_missing_weather_fails_closed():
    state = valid_state()
    state["telemetry"] = {"status": "INSUFFICIENT_EVIDENCE"}
    ok, errors = validate(state)
    assert not ok
    assert any("telemetry is missing" in item for item in errors)


def test_calendar_blocks_spray():
    state = valid_state()
    state["selected_action"] = "SPRAY"
    state["calendar"]["operational_windows"]["spraying_permitted"] = False
    assert not validate(state)[0]


def test_duplicate_observation_does_not_corroborate():
    state = valid_state()
    state["evidence_store"]["EVID-B"]["observation_key"] = "sentinel:ndvi:1"
    assert not validate(state)[0]


def test_unsupported_action_fails():
    state = valid_state()
    state["selected_action"] = "HARVEST"
    assert not validate(state)[0]


def test_one_citation_fails():
    state = valid_state()
    state["evidence_ids"] = ["EVID-A"]
    assert not validate(state)[0]


def test_empty_rationale_fails():
    state = valid_state()
    state["rationale"] = "  "
    assert not validate(state)[0]
