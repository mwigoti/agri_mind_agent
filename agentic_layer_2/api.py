from __future__ import annotations

import asyncio
import hmac
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .audit import AuditLog
from .config import settings
from .graph import create_graph, new_state, resume_graph
from .tool_adapter import MCPTools


class AdvisoryRequest(BaseModel):
    plot_id: str = Field(min_length=1, max_length=100)
    thread_id: str | None = None


class DecisionRequest(BaseModel):
    verdict: str
    reason: str | None = None
    decision_id: str | None = None


audit = AuditLog(settings.audit_path)
tools = MCPTools(audit)
graph = None
saver = None
saver_context = None
decision_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global graph, saver, saver_context
    if not settings.demo_mode:
        await tools.discover()
    graph, saver, saver_context = await create_graph(audit, tools)
    yield
    if saver_context is not None:
        await saver_context.__aexit__(None, None, None)


app = FastAPI(title="AgriMind Layer 2", version="0.1.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
async def root() -> HTMLResponse:
    return HTMLResponse("<meta http-equiv='refresh' content='0; url=/dashboard' />")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>AgriMind Dashboard</title>
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
      <style>
        :root {
          --bg: #0b1020;
          --panel: #121b2e;
          --panel-2: #1c2944;
          --line: #2d3d5d;
          --text: #edf3ff;
          --muted: #9db3d9;
          --green: #5dd39e;
          --amber: #f7c66f;
          --red: #f77f7f;
          --blue: #73b8ff;
          --purple: #a78bfa;
        }
        * { box-sizing: border-box; }
        body {
          margin: 0;
          font-family: Arial, sans-serif;
          background: radial-gradient(circle at top, #18284a, #0b1020 45%);
          color: var(--text);
        }
        .container { max-width: 1300px; margin: 0 auto; padding: 24px; }
        .header {
          display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 20px; border-bottom: 1px solid var(--line); padding-bottom: 12px;
        }
        .app-shell {
          display: flex; min-height: 100vh;
        }
        .sidebar {
          width: 220px; background: rgba(12,18,30,0.95); border-right: 1px solid var(--line);
          padding: 20px 16px; position: sticky; top: 0; height: 100vh;
        }
        .sidebar h3 {
          margin: 0 0 20px; font-size: 0.8rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted);
        }
        .nav-item {
          display: flex; align-items: center; gap: 10px; border: 1px solid transparent; border-radius: 10px; padding: 10px 12px;
          margin-bottom: 8px; color: var(--text); text-decoration: none; background: rgba(255,255,255,0.02);
        }
        .nav-item.active {
          background: rgba(115, 184, 255, 0.14); border-color: rgba(115,184,255,0.4);
        }
        .nav-dot {
          width: 9px; height: 9px; border-radius: 50%; background: var(--green);
        }
        .main {
          flex: 1; padding: 20px;
        }
        h1 { margin: 0; font-size: 1.9rem; }
        .badge {
          background: rgba(115, 184, 255, 0.15); border: 1px solid var(--line);
          color: var(--blue); border-radius: 999px; padding: 8px 12px; font-size: 0.82rem; font-weight: bold;
        }
        .grid {
          display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px;
          margin-top: 18px;
        }
        .card {
          background: rgba(18, 27, 46, 0.92); border: 1px solid var(--line);
          border-radius: 16px; padding: 18px; box-shadow: 0 10px 24px rgba(0,0,0,0.18);
        }
        .card h2 { margin-top: 0; margin-bottom: 12px; font-size: 1.15rem; }
        #map {
          width: 100%; height: 390px; border-radius: 16px; overflow: hidden; border: 1px solid var(--line);
          background: #0e1e2d;
        }
        .legend {
          display: flex; gap: 12px; flex-wrap: wrap; margin-top: 12px; color: var(--muted);
          font-size: 0.8rem;
        }
        .legend span { display: inline-flex; align-items: center; }
        .legend i {
          width: 10px; height: 10px; display: inline-block; border-radius: 50%; margin-right: 8px;
        }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        .stat {
          background: linear-gradient(180deg, rgba(28,41,68,0.85), rgba(17,24,39,0.9)); border: 1px solid var(--line);
          border-radius: 12px; padding: 14px; min-height: 120px;
        }
        .stat .label { color: var(--muted); font-size: 0.72rem; text-transform: uppercase; }
        .stat .value { font-size: 1.6rem; font-weight: bold; margin-top: 8px; }
        .stat .trend {
          margin-top: 8px; color: var(--green); font-size: 0.8rem; font-weight: bold;
        }
        .chart-card {
          display: flex; align-items: center; gap: 18px;
        }
        .ring {
          width: 110px; height: 110px; border-radius: 50%;
          background: conic-gradient(var(--green) 0 78%, #1d2d4e 78% 100%);
          position: relative; flex-shrink: 0;
        }
        .ring::before {
          content: ""; position: absolute; inset: 15px; background: #0d1629; border-radius: 50%;
          border: 1px solid var(--line);
        }
        .ring span {
          position: absolute; inset: 0; display: grid; place-items: center; font-size: 1.3rem; font-weight: bold; z-index: 1;
        }
        .bars {
          display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; align-items: end; height: 140px; width: 100%;
        }
        .bar-wrap { display: flex; flex-direction: column; align-items: center; justify-content: end; gap: 8px; height: 100%; }
        .bar {
          width: 100%; border-radius: 999px 999px 0 0; background: linear-gradient(180deg, var(--blue), var(--purple));
          min-height: 30px; box-shadow: inset 0 -6px 12px rgba(0,0,0,0.2);
        }
        .bar-label { color: var(--muted); font-size: 0.7rem; }
        .queue-list { list-style: none; padding: 0; margin: 0; }
        .queue-list li {
          display: flex; align-items: center; justify-content: space-between; gap: 10px;
          border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin-top: 10px;
          background: rgba(255,255,255,0.02);
        }
        .status-dot {
          width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 8px;
        }
        .dot-green { background: var(--green); }
        .dot-amber { background: var(--amber); }
        .dot-red { background: var(--red); }
        .timeline {
          display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 14px;
        }
        .timeline-step {
          background: rgba(115,184,255,0.06); border: 1px solid var(--line); border-radius: 12px; padding: 12px;
        }
        .timeline-step strong { display: block; margin-bottom: 8px; }
        .timeline-step small { color: var(--muted); }
        label { display: block; font-size: 0.82rem; margin-bottom: 8px; color: var(--muted); }
        input, select, textarea, button {
          width: 100%; border-radius: 10px; border: 1px solid var(--line); background: #0e172a; color: var(--text);
          padding: 10px 12px; margin-bottom: 12px; font-size: 0.96rem;
        }
        button {
          cursor: pointer; background: linear-gradient(135deg, #3b82f6, #2563eb); border: none; font-weight: bold;
        }
        button.secondary {
          background: linear-gradient(135deg, #f59e0b, #d97706);
        }
        textarea { min-height: 110px; resize: vertical; }
        .result {
          margin-top: 12px; background: rgba(255,255,255,0.02); border: 1px solid var(--line); border-radius: 10px;
          padding: 12px; font-family: monospace; white-space: pre-wrap; line-height: 1.5; color: var(--muted);
        }
        .row { display: flex; gap: 12px; }
        .row > * { flex: 1; }
      </style>
    </head>
    <body>
      <div class="app-shell">
        <aside class="sidebar">
          <h3>AgriMind</h3>
          <a href="#" class="nav-item active"><span class="nav-dot"></span>Overview</a>
          <a href="#" class="nav-item"><span class="nav-dot" style="background: var(--blue);"></span>Fields</a>
          <a href="#" class="nav-item"><span class="nav-dot" style="background: var(--amber);"></span>Reviews</a>
          <a href="#" class="nav-item"><span class="nav-dot" style="background: var(--red);"></span>Alerts</a>
        </aside>
        <main class="main">
          <div class="container" style="padding:0;">
            <div class="header">
              <h1>AgriMind Dashboard</h1>
              <span class="badge">Operations overview</span>
            </div>

            <div class="stats" style="margin-bottom: 18px;">
              <div class="stat">
                <div class="label">field health</div>
                <div class="value">78%</div>
                <div class="trend">▲ 12% vs last week</div>
              </div>
              <div class="stat">
                <div class="label">water stress</div>
                <div class="value">32%</div>
                <div class="trend" style="color: var(--amber);">▼ 7% improvement</div>
              </div>
              <div class="stat">
                <div class="label">pending review</div>
                <div class="value">12</div>
                <div class="trend">4 high priority</div>
              </div>
              <div class="stat">
                <div class="label">yield potential</div>
                <div class="value">4.8 t/ha</div>
                <div class="trend" style="color: var(--blue);">forecast</div>
              </div>
            </div>

            <div class="grid">
              <div class="card" style="grid-column: 1 / -1;">
                <h2>Farm map overview</h2>
                <div id="map" aria-label="field map"></div>
                <div class="legend" style="margin-top: 12px;">
                  <span><i style="background: var(--green);"></i> Healthy</span>
                  <span><i style="background: var(--amber);"></i> Monitor</span>
                  <span><i style="background: var(--red);"></i> Alert</span>
                </div>
              </div>

              <div class="card chart-card">
                <div class="ring"><span>78%</span></div>
                <div style="flex: 1;">
                  <h2>Field health</h2>
                  <div style="color: var(--muted); line-height: 1.6;">
                    <strong style="color: var(--text);">Healthy growth trajectory</strong><br />
                    Moisture is adequate and the crop remains within the safe window for flowering.
                  </div>
                </div>
              </div>

              <div class="card">
                <h2>Crop trend</h2>
                <div class="bars">
                  <div class="bar-wrap"><div class="bar" style="height: 42%;"></div><div class="bar-label">Jan</div></div>
                  <div class="bar-wrap"><div class="bar" style="height: 58%;"></div><div class="bar-label">Feb</div></div>
                  <div class="bar-wrap"><div class="bar" style="height: 64%;"></div><div class="bar-label">Mar</div></div>
                  <div class="bar-wrap"><div class="bar" style="height: 74%;"></div><div class="bar-label">Apr</div></div>
                  <div class="bar-wrap"><div class="bar" style="height: 82%;"></div><div class="bar-label">May</div></div>
                </div>
              </div>

              <div class="card" style="grid-column: 1 / -1;">
                <h2>Advisory queue</h2>
                <ul class="queue-list">
                  <li><span><span class="status-dot dot-green"></span>KE-001 · Irrigation scheduling</span><strong>Ready</strong></li>
                  <li><span><span class="status-dot dot-amber"></span>KE-014 · Foliar spray review</span><strong>Review</strong></li>
                  <li><span><span class="status-dot dot-red"></span>KE-032 · Risk alert: heat stress</span><strong>Escalated</strong></li>
                </ul>
                <div class="timeline">
                  <div class="timeline-step"><strong>Planting</strong><small>Complete</small></div>
                  <div class="timeline-step"><strong>Vegetative</strong><small>Healthy</small></div>
                  <div class="timeline-step"><strong>Flowering</strong><small>Monitoring</small></div>
                  <div class="timeline-step"><strong>Harvest</strong><small>Projected</small></div>
                </div>
              </div>

              <div class="card">
                <h2>Plot Status</h2>
                <div class="row">
                  <div style="flex: 1">
                    <label for="plotId">Plot ID</label>
                    <input id="plotId" value="KE-001" placeholder="KE-001" />
                  </div>
                  <div style="display:flex; align-items:flex-end; min-width:130px;">
                    <button id="loadStatusBtn">Load status</button>
                  </div>
                </div>
                <div id="statusResult" class="result">Ready</div>
              </div>

              <div class="card">
                <h2>Health & Ranking</h2>
                <button id="rankingBtn">Load ranking</button>
                <div id="rankingResult" class="result">Waiting</div>
              </div>

              <div class="card" style="grid-column: 1 / -1;">
                <h2>Advisory Queue</h2>
                <div class="row">
                  <div>
                    <label for="action">Recommended Action</label>
                    <select id="action">
                      <option>HOLD</option>
                      <option>SPRAY</option>
                      <option>IRRIGATE</option>
                      <option>HARVEST</option>
                    </select>
                  </div>
                  <div>
                    <label for="plotAdvisory">Plot ID</label>
                    <input id="plotAdvisory" value="KE-001" />
                  </div>
                </div>
                <label for="reason">Reasoning</label>
                <textarea id="reason">Use field observations and evidence to advise the farmer.</textarea>
                <button id="createAdvisoryBtn">Create advisory</button>
                <div id="advisoryResult" class="result">Waiting</div>
              </div>

              <div class="card" style="grid-column: 1 / -1;">
                <h2>Officer Review</h2>
                <div class="row">
                  <div>
                    <label for="threadId">Thread ID</label>
                    <input id="threadId" placeholder="paste thread id" />
                  </div>
                  <div>
                    <label for="decision">Verdict</label>
                    <select id="decision">
                      <option>APPROVE</option>
                      <option>REJECT</option>
                    </select>
                  </div>
                </div>
                <button class="secondary" id="reviewBtn">Submit review</button>
                <div id="reviewResult" class="result">Waiting</div>
              </div>
            </div>
          </div>
        </main>
      </div>

      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
      <script>
        const token = 'demo-token';
        const baseUrl = 'http://127.0.0.1:8003';
        const map = L.map('map').setView([-1.25, 36.82], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        const riskColors = {
          healthy: '#5dd39e',
          warning: '#f7c66f',
          alert: '#f77f7f'
        };

        const layers = L.layerGroup().addTo(map);

        function updateStatus(label, risk) {
          const statusMap = {
            healthy: 'Healthy',
            warning: 'Monitor',
            alert: 'Alert'
          };
          document.getElementById('plotId').value = String(label).toUpperCase().replace(/\s+/g, '-');
          document.getElementById('plotAdvisory').value = String(label).toUpperCase().replace(/\s+/g, '-');
          document.getElementById('statusResult').textContent = `${label}: ${statusMap[risk] || 'Healthy'} risk state`;
        }

        async function loadFieldMap() {
          const result = await fetch('/api/fields/map');
          const data = await result.json();
          const features = data.features || [];
          layers.clearLayers();

          if (!features.length) {
            return;
          }

          const polygons = L.geoJSON(data, {
            style: (feature) => ({
              color: riskColors[feature.properties?.risk || 'healthy'],
              weight: 2,
              opacity: 0.9,
              fillColor: riskColors[feature.properties?.risk || 'healthy'],
              fillOpacity: 0.28
            }),
            onEachFeature: (feature, layer) => {
              const props = feature.properties || {};
              layer.bindPopup(`<strong>${props.name || 'Field'}</strong><br/>Risk: ${props.risk || 'healthy'}<br/>Area: ${props.area || 'n/a'} ha`);
              layer.on('click', () => updateStatus(props.name || props.id || 'FIELD', props.risk || 'healthy'));
            }
          });

          polygons.addTo(layers);
          const bounds = polygons.getBounds();
          if (bounds && bounds.isValid()) {
            map.fitBounds(bounds.pad(0.35));
          }
        }

        loadFieldMap();

        async function apiFetch(url, options = {}) {
          const res = await fetch(url, {
            ...options,
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
              ...(options.headers || {})
            }
          });
          const text = await res.text();
          try {
            return { ok: res.ok, data: JSON.parse(text), status: res.status };
          } catch {
            return { ok: res.ok, data: text, status: res.status };
          }
        }

        document.getElementById('loadStatusBtn').addEventListener('click', async () => {
          const plotId = document.getElementById('plotId').value;
          const result = await apiFetch(`${baseUrl}/api/advisories`, {
            method: 'POST',
            body: JSON.stringify({ plot_id: plotId })
          });
          document.getElementById('statusResult').textContent = JSON.stringify(result, null, 2);
          if (result.ok && result.data.thread_id) {
            document.getElementById('threadId').value = result.data.thread_id;
          }
        });

        document.getElementById('rankingBtn').addEventListener('click', async () => {
          const result = await apiFetch(`${baseUrl}/api/demo/ranking`);
          document.getElementById('rankingResult').textContent = JSON.stringify(result, null, 2);
        });

        document.getElementById('createAdvisoryBtn').addEventListener('click', async () => {
          const plotId = document.getElementById('plotAdvisory').value;
          const action = document.getElementById('action').value;
          const reason = document.getElementById('reason').value;
          const result = await apiFetch(`${baseUrl}/api/advisories`, {
            method: 'POST',
            body: JSON.stringify({ plot_id: plotId })
          });
          const threadId = result.ok ? result.data.thread_id : '';
          document.getElementById('threadId').value = threadId;
          document.getElementById('advisoryResult').textContent = JSON.stringify(result, null, 2);
          if (threadId) {
            const reviewResult = await apiFetch(`${baseUrl}/api/advisories/${threadId}/decide`, {
              method: 'POST',
              body: JSON.stringify({ verdict: document.getElementById('decision').value, reason: reason + ' | action=' + action })
            });
            document.getElementById('reviewResult').textContent = JSON.stringify(reviewResult, null, 2);
          }
        });

        document.getElementById('reviewBtn').addEventListener('click', async () => {
          const threadId = document.getElementById('threadId').value;
          const verdict = document.getElementById('decision').value;
          const result = await apiFetch(`${baseUrl}/api/advisories/${threadId}/decide`, {
            method: 'POST',
            body: JSON.stringify({ verdict: verdict, reason: 'Officer reviewed in dashboard' })
          });
          document.getElementById('reviewResult').textContent = JSON.stringify(result, null, 2);
        });
      </script>
    </body>
    </html>
    ''' )


def require_api(authorization: str | None = Header(default=None)) -> str:
    expected = settings.api_bearer_token
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(401, detail={"error": "unauthenticated"}, headers={"WWW-Authenticate": "Bearer"})
    return "api-client"


def require_reviewer(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, detail={"error": "unauthenticated"}, headers={"WWW-Authenticate": "Bearer"})
    supplied = authorization[7:]
    for item in settings.reviewer_tokens.split(","):
        if ":" not in item:
            continue
        identity, token = item.split(":", 1)
        if hmac.compare_digest(supplied, token) and identity.strip():
            return identity.strip()
    raise HTTPException(401, detail={"error": "unauthenticated"}, headers={"WWW-Authenticate": "Bearer"})


def _synthetic_map_features() -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "north-block", "name": "North Block", "risk": "healthy", "area": 48.2},
                "geometry": {"type": "Polygon", "coordinates": [[ [36.78, -1.18], [36.82, -1.18], [36.82, -1.22], [36.78, -1.22], [36.78, -1.18] ]]}
            },
            {
                "type": "Feature",
                "properties": {"id": "south-block", "name": "South Block", "risk": "warning", "area": 39.7},
                "geometry": {"type": "Polygon", "coordinates": [[ [36.79, -1.25], [36.84, -1.25], [36.84, -1.29], [36.79, -1.29], [36.79, -1.25] ]]}
            },
            {
                "type": "Feature",
                "properties": {"id": "irrigation-zone", "name": "Irrigation Zone", "risk": "alert", "area": 51.4},
                "geometry": {"type": "Polygon", "coordinates": [[ [36.81, -1.21], [36.87, -1.21], [36.87, -1.26], [36.81, -1.26], [36.81, -1.21] ]]}
            },
        ],
    }


def _field_map_from_db() -> dict[str, Any] | None:
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AgriVision.settings")
        import django
        django.setup()
        from base.models import Field

        fields = list(Field.objects.all()[:20])
        features: list[dict[str, Any]] = []
        for field in fields:
            geometry = getattr(field, "geometry", None)
            if geometry is None:
                continue
            coordinates = json.loads(geometry.geojson)
            features.append({
                "type": "Feature",
                "properties": {
                    "id": field.id,
                    "name": field.name,
                    "risk": "healthy" if (field.area or 0) > 0 else "warning",
                    "area": float(field.area or 0),
                },
                "geometry": coordinates,
            })
        if features:
            return {"type": "FeatureCollection", "features": features}
    except Exception:
        return None
    return None


@app.get("/api/fields/map")
async def get_map_fields() -> dict[str, Any]:
    data = _field_map_from_db() or _synthetic_map_features()
    return data


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "mode": "synthetic_demo" if settings.demo_mode else "integrated", "model_configured": bool(settings.hf_token), "mcp_discovered": bool(tools.contracts) if not settings.demo_mode else False}


@app.post("/api/advisories", status_code=202)
async def start_advisory(payload: AdvisoryRequest, _: str = Depends(require_api)) -> dict[str, Any]:
    if graph is None:
        raise HTTPException(503, detail={"error": "workflow_not_ready"})
    state = new_state(payload.plot_id, payload.thread_id)
    config = {"configurable": {"thread_id": state["thread_id"]}}
    try:
        result = await graph.ainvoke(state, config=config)
    except Exception as exc:
        audit.write({"event": "workflow_failure", "execution_id": state["execution_id"], "thread_id": state["thread_id"], "error": type(exc).__name__})
        raise HTTPException(502, detail={"error": "workflow_failed", "thread_id": state["thread_id"]}) from exc
    return {"thread_id": state["thread_id"], "execution_id": state["execution_id"], "status": result.get("status"), "advisory": result.get("advisory_draft"), "review": result.get("review_prompt"), "errors": result.get("errors", [])}


@app.get("/api/advisories/{thread_id}")
async def get_advisory(thread_id: str, _: str = Depends(require_api)) -> dict[str, Any]:
    if graph is None:
        raise HTTPException(503, detail={"error": "workflow_not_ready"})
    state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    values = state.values
    if not values:
        raise HTTPException(404, detail={"error": "not_found"})
    return {key: values.get(key) for key in ("execution_id", "thread_id", "plot_id", "status", "selected_action", "rationale", "evidence_ids", "advisory_draft", "officer_decision", "officer_identity", "decision_timestamp", "simulated_sms", "errors")}


@app.post("/api/advisories/{thread_id}/decide")
async def decide(thread_id: str, payload: DecisionRequest, officer: str = Depends(require_reviewer)) -> dict[str, Any]:
    if graph is None:
        raise HTTPException(503, detail={"error": "workflow_not_ready"})
    verdict = payload.verdict.upper()
    if verdict not in {"APPROVE", "REJECT"}:
        raise HTTPException(422, detail={"error": "invalid_verdict"})
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    values = state.values
    if not values:
        raise HTTPException(404, detail={"error": "not_found"})
    if values.get("status") != "PENDING_APPROVAL" or not state.next:
        raise HTTPException(409, detail={"error": "execution_not_pending"})
    async with decision_lock:
        # Re-read under the process lock so duplicate concurrent decisions are rejected.
        state = await graph.aget_state(config)
        values = state.values
        if values.get("status") != "PENDING_APPROVAL" or not state.next:
            raise HTTPException(409, detail={"error": "execution_not_pending"})
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            result = await resume_graph(graph, thread_id, {"verdict": verdict, "officer_identity": officer, "decision_timestamp": stamp, "reason": payload.reason, "decision_id": payload.decision_id})
        except Exception as exc:
            raise HTTPException(409, detail={"error": "decision_conflict"}) from exc
    return {"thread_id": thread_id, "status": result.get("status"), "decision": verdict, "officer_identity": officer, "decision_timestamp": stamp, "simulated_sms": result.get("simulated_sms")}


@app.get("/api/demo/ranking")
async def demo_ranking(_: str = Depends(require_api)) -> dict[str, Any]:
    if not settings.demo_mode:
        raise HTTPException(404, detail={"error": "demo_unavailable"})
    from .synthetic import ranking
    return {"label": "SYNTHETIC demonstration heuristic; not agronomic advice", "plots": ranking()}
