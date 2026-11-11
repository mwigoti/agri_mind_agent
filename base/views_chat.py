"""
AgriMind Chat Views.
Provides a chat page and API endpoint that proxies to the Layer 2 FastAPI
agentic service, with graceful rule-based fallback when the service is offline.
"""
from __future__ import annotations

import json
import logging
import os
import random
from typing import Any, Dict, List, Optional

import requests
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

LAYER2_BASE = os.getenv("AGRIMIND_AGENT_URL", "http://127.0.0.1:8001").rstrip("/")
LAYER2_TIMEOUT = int(os.getenv("AGRIMIND_AGENT_TIMEOUT", "12"))
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "dev-api-token")


# ---------------------------------------------------------------------------
# Page view
# ---------------------------------------------------------------------------

def chat_page(request):
    """Render the AgriMind chat interface."""
    return render(request, "chat.html")


# ---------------------------------------------------------------------------
# Rule-based fallback responses
# ---------------------------------------------------------------------------

FALLBACK_RESPONSES_EN = {
    "weather": [
        "Based on recent patterns, expect moderate rainfall this week. "
        "Consider delaying any fertilizer application until after the rains. "
        "Keep an eye on your drainage channels.",
        "Current forecasts suggest warming temperatures over the next 5 days. "
        "Ensure your irrigation system is ready and consider mulching to conserve soil moisture.",
    ],
    "health": [
        "Regular field scouting is essential. Look for yellowing leaves (possible nitrogen deficiency), "
        "wilting (water stress), or spots (fungal infection). Take photos for comparison over time.",
        "Your crop health can be assessed using NDVI imagery. Generally, NDVI > 0.6 indicates healthy vegetation. "
        "Schedule a satellite analysis from your dashboard for detailed insights.",
    ],
    "yield": [
        "Yield prediction depends on several factors: planting density, soil fertility, rainfall distribution, "
        "and pest pressure. For a more accurate estimate, run a full field analysis from your dashboard.",
        "Historical data suggests that maintaining consistent irrigation and timely fertilizer application "
        "can improve yields by 15-25%. Consider soil testing to optimize your inputs.",
    ],
    "soil": [
        "Soil health is fundamental. Key indicators include pH (ideal: 6.0-7.0 for most crops), "
        "organic matter content, and nutrient levels (N, P, K). Regular soil testing every season is recommended.",
        "Consider cover cropping and crop rotation to improve soil structure and fertility naturally. "
        "Composting farm residues can significantly boost organic matter content.",
    ],
    "pest": [
        "Integrated Pest Management (IPM) is the most sustainable approach. Start with cultural controls "
        "(crop rotation, resistant varieties), then biological controls, and use chemical pesticides only as a last resort.",
        "Common signs of pest damage include holes in leaves, wilting, discoloration, and stunted growth. "
        "Early detection through regular scouting is key to effective management.",
    ],
    "irrigation": [
        "Efficient irrigation depends on crop stage, soil type, and weather. Sandy soils need more frequent, "
        "lighter watering while clay soils benefit from deeper, less frequent irrigation.",
        "Consider drip irrigation for water efficiency — it can reduce water use by up to 50% compared to "
        "flood irrigation while improving yields through targeted root-zone delivery.",
    ],
    "fertilizer": [
        "Balanced fertilization based on soil test results is key. Over-application wastes money and can "
        "harm the environment. Split applications — applying fertilizer in stages — improve nutrient uptake.",
        "For most crops, nitrogen is needed during vegetative growth, phosphorus for root development, "
        "and potassium for fruiting. Micronutrients like zinc and boron are also important.",
    ],
    "recommend": [
        "Based on general best practices: 1) Test your soil before planting, 2) Use certified seeds, "
        "3) Follow recommended spacing, 4) Apply fertilizer based on soil test results, "
        "5) Scout for pests weekly, 6) Harvest at the right maturity stage.",
    ],
    "crop": [
        "Crop selection should consider your local climate, soil type, market demand, and available resources. "
        "Diversifying crops reduces risk and can improve soil health through rotation.",
    ],
}

FALLBACK_RESPONSES_SW = {
    "weather": [
        "Kulingana na mifumo ya hivi karibuni, tarajia mvua ya wastani wiki hii. "
        "Fikiria kuchelewesha uwekaji wa mbolea hadi baada ya mvua. "
        "Fuatilia njia zako za mifereji ya maji.",
    ],
    "health": [
        "Ukaguzi wa shamba mara kwa mara ni muhimu. Tafuta majani yanayogeuka njano "
        "(upungufu wa nitrojeni), kunyauka (ukosefu wa maji), au madoa (ugonjwa wa fangasi). "
        "Piga picha kwa ulinganisho.",
    ],
    "yield": [
        "Utabiri wa mavuno unategemea mambo kadhaa: msongamano wa upanzi, rutuba ya udongo, "
        "usambazaji wa mvua, na shinikizo la wadudu. Fanya uchambuzi kamili kutoka kwenye dashibodi yako.",
    ],
    "soil": [
        "Afya ya udongo ni msingi. Viashiria muhimu ni pamoja na pH (bora: 6.0-7.0 kwa mazao mengi), "
        "kiwango cha madini, na viwango vya virutubisho. Pima udongo kila msimu.",
    ],
    "recommend": [
        "Kulingana na mazoea bora: 1) Pima udongo wako kabla ya kupanda, 2) Tumia mbegu zilizothibitishwa, "
        "3) Fuata nafasi zilizopendekezwa, 4) Weka mbolea kulingana na matokeo ya upimaji wa udongo.",
    ],
}

DEFAULT_EN = (
    "I'm AgriMind, your agricultural assistant. I can help you with weather updates, "
    "crop health assessment, yield predictions, soil analysis, pest management, "
    "irrigation advice, and fertilizer recommendations. What would you like to know?"
)
DEFAULT_SW = (
    "Mimi ni AgriMind, msaidizi wako wa kilimo. Ninaweza kukusaidia na masasisho ya hali ya hewa, "
    "tathmini ya afya ya mazao, utabiri wa mavuno, uchambuzi wa udongo, usimamizi wa wadudu, "
    "ushauri wa umwagiliaji, na mapendekezo ya mbolea. Ungependa kujua nini?"
)

KEYWORD_MAP = {
    "weather": ["weather", "rain", "temperature", "forecast", "climate", "hali ya hewa", "mvua"],
    "health": ["health", "ndvi", "disease", "yellow", "wilt", "afya", "ugonjwa"],
    "yield": ["yield", "harvest", "production", "mavuno", "uzalishaji"],
    "soil": ["soil", "ph", "nutrient", "organic", "udongo", "rutuba"],
    "pest": ["pest", "insect", "bug", "worm", "fungus", "wadudu"],
    "irrigation": ["irrigation", "water", "drip", "umwagiliaji", "maji"],
    "fertilizer": ["fertilizer", "npk", "nitrogen", "phosphorus", "mbolea"],
    "recommend": ["recommend", "advice", "suggest", "best practice", "pendekezo", "analyze", "check"],
    "crop": ["crop", "plant", "seed", "variety", "mazao", "mbegu"],
}


def _match_topic(message: str) -> Optional[str]:
    """Return the first matching topic keyword category."""
    lower = message.lower()
    for topic, keywords in KEYWORD_MAP.items():
        if any(kw in lower for kw in keywords):
            return topic
    return None


def _get_fallback_response(message: str, language: str = "en") -> Dict[str, Any]:
    """Generate a rule-based fallback response when Layer 2 is unavailable."""
    topic = _match_topic(message)
    responses = FALLBACK_RESPONSES_SW if language == "sw" else FALLBACK_RESPONSES_EN

    if topic and topic in responses:
        text = random.choice(responses[topic])
        tools = [f"local_{topic}_knowledge"]
    else:
        text = DEFAULT_SW if language == "sw" else DEFAULT_EN
        tools = ["general_knowledge"]

    return {
        "response": text,
        "tools_used": tools,
        "confidence": 0.65,
        "source": "local_fallback",
    }


def _proxy_to_layer2(message: str, field_id: Optional[int] = None, language: str = "en") -> Optional[Dict[str, Any]]:
    """Attempt to proxy the chat message to the Layer 2 FastAPI service."""
    try:
        payload = {"plot_id": str(field_id) if field_id else "general"}
        resp = requests.post(
            f"{LAYER2_BASE}/api/advisories",
            json=payload,
            headers={
                "Authorization": f"Bearer {API_BEARER_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=LAYER2_TIMEOUT,
        )
        if resp.status_code in (200, 202):
            data = resp.json()
            advisory_text = data.get("advisory", data.get("status", ""))
            return {
                "response": advisory_text or f"AgriMind is processing your request. Thread: {data.get('thread_id', 'N/A')}",
                "tools_used": data.get("tools_used", ["agrimind_agent"]),
                "confidence": 0.92,
                "source": "agrimind_layer2",
                "thread_id": data.get("thread_id"),
            }
        return None
    except Exception as exc:
        logger.debug("Layer 2 proxy failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Chat API endpoint
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name="dispatch")
class ChatAPIView(View):
    """
    POST /api/agent/chat/
    Accepts: {"message": "...", "field_id": optional int, "language": "en"|"sw"}
    Returns: {"response": "...", "tools_used": [...], "confidence": float}
    """

    def post(self, request, *args, **kwargs):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse(
                {"error": "Invalid JSON body"}, status=400
            )

        message = body.get("message", "").strip()
        if not message:
            return JsonResponse(
                {"error": "Message is required"}, status=400
            )

        field_id = body.get("field_id")
        language = body.get("language", "en")

        # Try Layer 2 first
        result = _proxy_to_layer2(message, field_id=field_id, language=language)

        if result is None:
            # Fallback to local rule-based responses
            result = _get_fallback_response(message, language=language)

        return JsonResponse(result)
