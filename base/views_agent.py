"""
AgriMind Agent Advisory Views for AgriVision.
Bridges Django field intelligence and web UI to the LangGraph AgriMind agent layer.
"""
from __future__ import annotations

import json
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from base.services.agrimind_client import AgriMindClient


class AgriMindStatusView(APIView):
    """Healthcheck endpoint for the connected AgriMind LangGraph Agent."""
    def get(self, request, *args, **kwargs):
        client = AgriMindClient()
        online = client.is_agent_online()
        return Response({
            "agent_online": online,
            "agent_url": client.base_url,
            "status": "connected" if online else "database_fallback_ready"
        }, status=status.HTTP_200_OK)


class AgriMindFieldAdvisoryView(APIView):
    """
    Dispatch field-level advisory to AgriMind LangGraph agent.
    If thread_id is provided, checks state; otherwise kicks off execution.
    """
    def post(self, request, field_id: int, *args, **kwargs):
        thread_id = request.data.get("thread_id") if hasattr(request, "data") else None
        client = AgriMindClient()
        result = client.request_advisory(plot_id=field_id, thread_id=thread_id)
        http_status = status.HTTP_202_ACCEPTED if result.get("status") == "RUNNING" else status.HTTP_200_OK
        return Response(result, status=http_status)

    def get(self, request, field_id: int, *args, **kwargs):
        thread_id = request.query_params.get("thread_id")
        if not thread_id:
            return Response(
                {"error": "Missing thread_id query parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        client = AgriMindClient()
        result = client.get_advisory(thread_id=thread_id)
        return Response(result, status=status.HTTP_200_OK)


class AgriMindDecisionView(APIView):
    """
    Human-in-the-loop decision endpoint.
    Agronomists approve or reject proposed crop interventions before SMS dispatch.
    """
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
        result = client.submit_decision(
            thread_id=thread_id,
            verdict=verdict,
            reason=reason,
            decision_id=decision_id,
        )
        return Response(result, status=status.HTTP_200_OK)


class AgriMindRankingsView(APIView):
    """Retrieve prioritized parcel risk rankings for operational planning."""
    def get(self, request, *args, **kwargs):
        client = AgriMindClient()
        rankings = client.get_prioritized_rankings()
        return Response({"plots": rankings}, status=status.HTTP_200_OK)

