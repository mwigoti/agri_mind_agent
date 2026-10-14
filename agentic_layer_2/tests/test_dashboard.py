from fastapi.testclient import TestClient

from agentic_layer_2.api import app

client = TestClient(app)


def test_dashboard_page_served():
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert 'AgriMind Dashboard' in response.text
    assert 'plot status' in response.text.lower()


def test_map_fields_endpoint_served():
    response = client.get('/api/fields/map')
    assert response.status_code == 200
    payload = response.json()
    assert payload['type'] == 'FeatureCollection'
    assert 'features' in payload
