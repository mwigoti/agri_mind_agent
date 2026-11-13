"""
AgriMind Agent Advisory Views for AgriVision.
Bridges Django field intelligence and web UI to the LangGraph AgriMind agent layer.
"""
from __future__ import annotations

import json
import requests
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from base.services.agrimind_client import AgriMindClient
from base.models import AdvisoryReview, Field


class AgriMindStatusView(APIView):
    """Healthcheck endpoint for the connected AgriMind LangGraph Agent."""
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        client = AgriMindClient()
        try:
            response = requests.get(f"{client.base_url}/health", timeout=client.timeout)
            health = response.json() if response.ok else {}
            online = response.ok and health.get("status") == "ok"
        except Exception:
            health, online = {}, False
        return Response({
            "agent_online": online,
            "agent_url": client.base_url,
            "status": health.get("mode", "unavailable"),
            "runtime": health.get("runtime", "unavailable"),
            "model_configured": health.get("model_configured", False),
            "mcp_discovered": health.get("mcp_discovered", False),
            "missing_configuration": health.get("missing_configuration", []),
        }, status=status.HTTP_200_OK)


class AgriMindFieldAdvisoryView(APIView):
    """
    Dispatch field-level advisory to AgriMind LangGraph agent.
    If thread_id is provided, checks state; otherwise kicks off execution.
    """
    permission_classes = [IsAuthenticated]
    def post(self, request, field_id: int, *args, **kwargs):
        field = get_object_or_404(Field, pk=field_id)
        if field.owner_id != request.user.id and not request.user.is_staff:
            return Response({"error": "You do not have access to this field."}, status=status.HTTP_403_FORBIDDEN)
        thread_id = request.data.get("thread_id") if hasattr(request, "data") else None
        client = AgriMindClient()
        result = client.request_advisory(plot_id=field_id, thread_id=thread_id)
        http_status = status.HTTP_202_ACCEPTED if result.get("status") == "RUNNING" else status.HTTP_200_OK
        return Response(result, status=http_status)

    def get(self, request, field_id: int, *args, **kwargs):
        field = get_object_or_404(Field, pk=field_id)
        if field.owner_id != request.user.id and not request.user.is_staff:
            return Response({"error": "You do not have access to this field."}, status=status.HTTP_403_FORBIDDEN)
        thread_id = request.query_params.get("thread_id")
        if not thread_id:
            return Response(
                {"error": "Missing thread_id query parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        client = AgriMindClient()
        result = client.get_advisory(thread_id=thread_id)
        if str(result.get("plot_id")) != str(field_id):
            return Response({"error": "Advisory thread does not belong to this field."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)


class AgriMindDecisionView(APIView):
    """
    Human-in-the-loop decision endpoint.
    Agronomists approve or reject proposed crop interventions before SMS dispatch.
    """
    permission_classes = [IsAuthenticated]
    def post(self, request, thread_id: str, *args, **kwargs):
        verdict = request.data.get("verdict", "").upper()
        reason = request.data.get("reason", "Approved by field officer")
        decision_id = request.data.get("decision_id")

        if verdict not in {"APPROVE", "REJECT"}:
            return Response(
                {"error": "Verdict must be either 'APPROVE' or 'REJECT'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = AgriMindClient()
        advisory = client.get_advisory(thread_id)
        if not advisory.get("plot_id"):
            return Response({"error": "Pending advisory was not found."}, status=status.HTTP_404_NOT_FOUND)
        field = get_object_or_404(Field, pk=advisory["plot_id"])
        if field.owner_id != request.user.id and not request.user.is_staff:
            return Response({"error": "You do not have permission to review this field."}, status=status.HTTP_403_FORBIDDEN)
        result = client.submit_decision(
            thread_id=thread_id,
            verdict=verdict,
            reason=reason,
            decision_id=decision_id,
        )
        if result.get("status") in {"SIMULATED_SMS_PREPARED", "REJECTED"}:
            review = AdvisoryReview.objects.filter(thread_id=thread_id).first()
            if review is None:
                review = AdvisoryReview(field=field, thread_id=thread_id)
            draft = advisory.get("advisory_draft") or {}
            review.field = field
            review.recommended_action = advisory.get("selected_action") or draft.get("recommended_action") or "HOLD"
            review.rationale = advisory.get("rationale") or draft.get("advisory_rationale") or ""
            review.evidence_ids = advisory.get("evidence_ids") or draft.get("evidence_ids") or []
            review.status = "approved" if verdict == "APPROVE" else "rejected"
            review.reviewer = request.user
            review.reviewer_comment = str(reason or "")
            review.decision_reason = str(reason or "")
            review.reviewed_at = timezone.now()
            review.save()
        return Response(result, status=status.HTTP_200_OK)


class AgriMindRankingsView(APIView):
    """Retrieve prioritized parcel risk rankings for operational planning."""
    def get(self, request, *args, **kwargs):
        client = AgriMindClient()
        rankings = client.get_prioritized_rankings()
        return Response({"plots": rankings}, status=status.HTTP_200_OK)

