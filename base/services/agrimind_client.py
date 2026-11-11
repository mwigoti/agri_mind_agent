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
        """Fetch prioritized farm parcels based on crop health and stress factors."""
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
            logger.warning("Ranking endpoint failed, returning fallback: %s", exc)
            return []

    def _fallback_advisory(self, plot_id: str | int) -> Dict[str, Any]:
        """Deterministic local fallback when the remote agent service is offline."""
        return {
            "thread_id": f"fallback-{plot_id}",
            "execution_id": f"exec-fallback-{plot_id}",
            "status": "OFFLINE_FALLBACK",
            "advisory": (
                f"Field #{plot_id} queued for local rule evaluation. "
                "Remote agent is currently offline; deterministic fallback active."
            ),
            "review": None,
            "errors": [],
        }

