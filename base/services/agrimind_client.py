"""
AgriMind Agent Client Service
Connects Django (Base) to the LangGraph Agentic Layer (agentic_layer_2).
Provides seamless field advisory dispatch, status querying, and human-in-the-loop decisions.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


def _db_field_summary(plot_id: str | int) -> Dict[str, Any]:
    """Build advisory context strictly from database records so offline mode still uses real field state."""
    try:
        from base.models import Field

        field = Field.objects.filter(pk=plot_id).select_related("owner").first()
        if field is None:
            return {
                "status": "NO_FIELD_RECORD",
                "advisory": f"No field record exists for plot {plot_id} in the database.",
                "field": None,
            }

        planting_activity = field.activities.filter(activity_type="planting").order_by("-date").first()
        crop_name = "Unregistered crop"
        if planting_activity and planting_activity.crop:
            crop_name = planting_activity.crop.name

        return {
            "status": "DB_FALLBACK",
            "thread_id": f"db-fallback-{field.id}",
            "execution_id": f"db-exec-{field.id}",
            "advisory": (
                f"Field '{field.name}' is available in the database. "
                f"Current crop record: {crop_name}. "
                "Use the saved field and crop records as the source of truth until the agent service is reachable."
            ),
            "field": {
                "id": field.id,
                "name": field.name,
                "area_ha": field.area,
                "owner": getattr(field.owner, "email", None),
            },
            "crop": {"name": crop_name},
        }
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("DB-backed fallback advisory generation failed: %s", exc)
        return {
            "status": "DB_FALLBACK_UNAVAILABLE",
            "thread_id": f"db-fallback-{plot_id}",
            "execution_id": f"db-exec-{plot_id}",
            "advisory": "Database-backed advisory data is unavailable right now.",
            "field": None,
        }


class AgriMindClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None,
        reviewer_token: Optional[str] = None,
        timeout: int = 10,
    ):
        self.base_url = (base_url or os.getenv("AGRIMIND_AGENT_URL", "http://127.0.0.1:8001")).rstrip("/")
        self.api_token = api_token or os.getenv("API_BEARER_TOKEN", "dev-api-token")
        self.reviewer_token = reviewer_token or os.getenv("REVIEWER_TOKEN", "dev-reviewer-token")
        self.timeout = timeout

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    @property
    def _reviewer_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.reviewer_token}",
            "Content-Type": "application/json",
        }

    def is_agent_online(self) -> bool:
        """Check if the Agentic Layer 2 service is healthy and reachable."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("AgriMind agent healthcheck failed: %s", exc)
            return False

    def request_advisory(self, plot_id: str | int, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Request a full multi-agent advisory run for a given field/plot.
        Returns the thread_id, execution_id, and pending status.
        """
        payload = {"plot_id": str(plot_id)}
        if thread_id:
            payload["thread_id"] = thread_id

        try:
            resp = requests.post(
                f"{self.base_url}/api/advisories",
                json=payload,
                headers=self._headers,
                timeout=self.timeout,
            )
            if resp.status_code in (200, 202):
                return resp.json()
            return {
                "status": "ERROR",
                "error": f"Agent returned HTTP {resp.status_code}: {resp.text}",
            }
        except Exception as exc:
            logger.warning("Could not reach AgriMind agent at %s: %s", self.base_url, exc)
            return self._fallback_advisory(plot_id)

    def get_advisory(self, thread_id: str) -> Dict[str, Any]:
        """Fetch the current state, draft, citations, and status for a thread."""
        try:
            resp = requests.get(
                f"{self.base_url}/api/advisories/{thread_id}",
                headers=self._headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"status": "NOT_FOUND", "error": resp.text}
        except Exception as exc:
            logger.warning("Failed to get advisory %s from agent: %s", thread_id, exc)
            return {"status": "UNAVAILABLE", "error": str(exc)}

    def submit_decision(
        self,
        thread_id: str,
        verdict: str,
        reason: Optional[str] = None,
        decision_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a human agronomist decision (APPROVE / REJECT) for a pending advisory.
        """
        payload = {
            "verdict": verdict.upper(),
            "reason": reason or "Reviewed by agronomist",
            "decision_id": decision_id,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/advisories/{thread_id}/decide",
                json=payload,
                headers=self._reviewer_headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"status": "ERROR", "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as exc:
            logger.error("Failed to submit decision for thread %s: %s", thread_id, exc)
            return {"status": "ERROR", "error": str(exc)}

    def get_prioritized_rankings(self) -> List[Dict[str, Any]]:
        """Fetch prioritized farm parcels based on crop health and stress factors from the database when live ranking is unavailable."""
        try:
            resp = requests.get(
                f"{self.base_url}/api/ranking",
                headers=self._headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("plots", [])
            return []
        except Exception as exc:
            logger.warning("Ranking endpoint failed, falling back to database-backed rankings: %s", exc)
            try:
                from base.models import Field, AnalysisResult

                rankings: List[Dict[str, Any]] = []
                for field in Field.objects.all().order_by("id")[:20]:
                    latest_result = (
                        AnalysisResult.objects.filter(field=field).order_by("-updated_at").first()
                    )
                    if latest_result is None:
                        continue
                    rankings.append({
                        "plot_id": str(field.id),
                        "field_name": field.name,
                        "priority": "medium",
                        "score": float(latest_result.ndvi_latest or 0.0),
                        "source": "database",
                    })
                return rankings
            except Exception:  # pragma: no cover - defensive guard
                return []

    def _fallback_advisory(self, plot_id: str | int) -> Dict[str, Any]:
        """Use the saved database record as the source of truth when the remote agent is offline."""
        fallback = _db_field_summary(plot_id)
        return {
            "thread_id": fallback.get("thread_id", f"db-fallback-{plot_id}"),
            "execution_id": fallback.get("execution_id", f"db-exec-{plot_id}"),
            "status": fallback.get("status", "DB_FALLBACK"),
            "advisory": fallback.get("advisory", "Database-backed advisory data is unavailable."),
            "field": fallback.get("field"),
            "crop": fallback.get("crop"),
            "review": None,
            "errors": [],
        }

