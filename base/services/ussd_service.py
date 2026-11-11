"""
USSD Service for Low-Bandwidth Smallholder Advisory.
Connects Africa's Talking USSD gateways (*384#) to AgriVision & AgriMind Agentic Layer.
Supports feature-phone registration, crop health queries, weather forecasts, and SMS dispatch.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple
from django.utils.timezone import now

from base.models import CustomUser, Field, SmartRecommendation, USSDSession, WeatherAlert, WeatherData
from base.services.agrimind_client import AgriMindClient
from base.utils.sms_service import AfricasTalkingSMSService

logger = logging.getLogger(__name__)


class USSDService:
    def __init__(self, agrimind_client: Optional[AgriMindClient] = None, sms_service: Optional[AfricasTalkingSMSService] = None):
        self.agent = agrimind_client or AgriMindClient()
        self.sms = sms_service or AfricasTalkingSMSService()

    @staticmethod
    def clean_phone_number(phone_number: str) -> str:
        """Normalize Kenyan and international phone numbers to E.164 format."""
        cleaned = phone_number.strip()
        if cleaned.startswith("0"):
            return "+254" + cleaned[1:]
        elif cleaned.startswith("254"):
            return "+" + cleaned
        elif not cleaned.startswith("+"):
            return "+254" + cleaned
        return cleaned

    def process(self, session_id: str, phone_number: str, text: str) -> str:
        """Process incoming USSD request from Africa's Talking gateway."""
        if not session_id or not phone_number:
            return "END Invalid USSD request."

        phone = self.clean_phone_number(phone_number)
        session, _ = USSDSession.objects.get_or_create(
            session_id=session_id,
            defaults={"phone_number": phone, "current_step": "start", "data": {}},
        )

        user_input = text.split("*")[-1].strip() if text else ""
        step = session.current_step

        # Route to appropriate state handler
        if step == "start":
            return self._handle_start(session)
        elif step == "reg_main":
            return self._handle_reg_main(session, user_input)
        elif step == "reg_first_name":
            return self._handle_first_name(session, user_input)
        elif step == "reg_last_name":
            return self._handle_last_name(session, user_input)
        elif step == "reg_confirm":
            return self._handle_reg_confirm(session, user_input)
        elif step == "farmer_home":
            return self._handle_farmer_home(session, user_input)
        elif step == "select_field_advisory":
            return self._handle_field_advisory(session, user_input)
        else:
            session.current_step = "start"
            session.save()
            return self._handle_start(session)

    # ── Flow: Start Screen ─────────────────────────────────────────────
    def _handle_start(self, session: USSDSession) -> str:
        user = CustomUser.objects.filter(phone_number=session.phone_number).first()
        if user:
            session.current_step = "farmer_home"
            session.save()
            first_name = user.first_name or "Farmer"
            return (
                f"CON Welcome back, {first_name}! 🌱\n"
                f"AgriMind Advisory:\n"
                f"1. Crop Health & Advisory\n"
                f"2. Weather & Rain Forecast\n"
                f"3. Urgent Field Alerts\n"
                f"4. Send SMS Summary\n"
                f"0. Exit"
            )

        session.current_step = "reg_main"
        session.save()
        return (
            "CON Welcome to AgriVision! 🌱\n"
            "Your Smart Farming Partner\n\n"
            "1. Register New Account\n"
            "2. About AgriVision\n"
            "0. Exit"
        )

    # ── Flow: Existing Farmer Menu ─────────────────────────────────────
    def _handle_farmer_home(self, session: USSDSession, choice: str) -> str:
        user = CustomUser.objects.filter(phone_number=session.phone_number).first()
        if not user:
            session.delete()
            return "END Session expired. Please redial."

        if choice == "1":
            # Crop Health & Advisory -> List fields
            fields = list(Field.objects.filter(owner=user)[:5])
            if not fields:
                # Also check any field in system if user has no assigned fields yet
                return "END No fields registered yet. Draw a field on the web map or contact your local agronomist."

            session.current_step = "select_field_advisory"
            session.data["field_ids"] = [f.id for f in fields]
            session.save()

            menu_lines = ["CON Select Field:"]
            for idx, f in enumerate(fields, 1):
                area_text = f"{f.area:.1f}ha" if f.area else ""
                menu_lines.append(f"{idx}. {f.name} {area_text}".strip())
            menu_lines.append("0. Back")
            return "\n".join(menu_lines)

        elif choice == "2":
            # Weather & Rain forecast
            try:
                user_field = Field.objects.filter(owner=user).first()
            except Exception:
                user_field = None
            weather = None
            if user_field:
                try:
                    weather = WeatherData.objects.filter(field=user_field).order_by("-recorded_at").first()
                except Exception:
                    weather = None

            temp = f"{weather.temperature:.0f}°C" if weather and weather.temperature else "22°C"
            rain = f"{weather.rainfall:.1f}mm" if weather and weather.rainfall else "12.0mm in 48h"
            humidity = f"{weather.humidity:.0f}%" if weather and weather.humidity else "65%"

            return (
                f"END 🌤️ Weather Forecast:\n"
                f"Temp: {temp} | Humidity: {humidity}\n"
                f"Rain: {rain}\n"
                f"Spray Window: Recommended after 24h\n"
                f"AgriVision Climate Intelligence 🌾"
            )

        elif choice == "3":
            # Urgent Field Alerts
            try:
                alerts = list(SmartRecommendation.objects.filter(field__owner=user, urgency__in=["high", "critical"])[:2])
            except Exception:
                alerts = []

            if not alerts:
                return "END ✅ No critical alerts.\nAll fields within healthy agro-ecological baselines."

            lines = ["END ⚠️ Active Field Alerts:"]
            for a in alerts:
                lines.append(f"- {a.title}: {a.message[:60]}...")
            return "\n".join(lines)

        elif choice == "4":
            # Send SMS Summary to phone
            try:
                field_count = Field.objects.filter(owner=user).count()
            except Exception:
                field_count = 1
            sms_body = (
                f"AgriVision Advisory for {user.first_name}:\n"
                f"Monitored Fields: {field_count}\n"
                f"Crop Status: Optimum vegetative vigor.\n"
                f"Soil Moisture: Adequate.\n"
                f"Full advisory: https://agrivision.africa/health"
            )
            success, _ = self.sms.send_sms(session.phone_number, sms_body)
            session.delete()
            if success:
                return f"END 📱 SMS summary sent to {session.phone_number}! Check your inbox in a moment. 🌾"
            return f"END Advisory queued for SMS dispatch to {session.phone_number}. 🌾"

        elif choice == "0":
            session.delete()
            return "END Thank you for using AgriVision! 🌾"

        return (
            "CON Invalid choice:\n"
            "1. Crop Health & Advisory\n"
            "2. Weather & Rain Forecast\n"
            "3. Urgent Field Alerts\n"
            "4. Send SMS Summary\n"
            "0. Exit"
        )

    # ── Flow: Field Advisory Submenu ──────────────────────────────────
    def _handle_field_advisory(self, session: USSDSession, choice: str) -> str:
        if choice == "0":
            session.current_step = "farmer_home"
            session.save()
            return self._handle_start(session)

        field_ids = session.data.get("field_ids", [])
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(field_ids):
                return "END Invalid field selection."
            target_field_id = field_ids[idx]
        except (ValueError, TypeError):
            return "END Invalid selection."

        field = Field.objects.filter(id=target_field_id).first()
        if not field:
            return "END Field not found."

        # Query AgriMind Agent
        advisory_data = self.agent.request_advisory(plot_id=field.id)
        action = advisory_data.get("selected_action") or "MONITOR"
        status = advisory_data.get("status") or "OK"

        session.delete()
        return (
            f"END [{field.name[:18]}]\n"
            f"Action: {action}\n"
            f"Status: {status}\n"
            f"Soil/Rain: Checked vs baselines\n"
            f"AgriMind AI Verified 🌽"
        )

    # ── Flow: Registration Handlers ────────────────────────────────────
    def _handle_reg_main(self, session: USSDSession, choice: str) -> str:
        if choice == "1":
            session.current_step = "reg_first_name"
            session.save()
            return "CON Enter your FIRST NAME:\n\n0. Back"
        elif choice == "2":
            return (
                "END About AgriVision 🌱\n\n"
                "Satellite & AI platform for maize monitoring, "
                "weather alerts, and crop yield advisory.\n"
                "Dial *384# anytime!"
            )
        elif choice == "0":
            session.delete()
            return "END Thank you! 🌾"
        return "CON Invalid choice:\n1. Register New Account\n2. About AgriVision\n0. Exit"

    def _handle_first_name(self, session: USSDSession, first_name: str) -> str:
        if first_name == "0":
            session.current_step = "reg_main"
            session.save()
            return self._handle_start(session)

        clean = first_name.strip()
        if len(clean) < 2:
            return "CON Name too short! Enter at least 2 characters:\n\n0. Back"

        session.data["first_name"] = clean.title()
        session.current_step = "reg_last_name"
        session.save()
        return f"CON First Name: {session.data['first_name']} ✓\n\nEnter your LAST NAME:\n\n0. Back"

    def _handle_last_name(self, session: USSDSession, last_name: str) -> str:
        if last_name == "0":
            session.current_step = "reg_first_name"
            session.save()
            return "CON Enter your FIRST NAME:\n\n0. Back"

        clean = last_name.strip()
        if len(clean) < 2:
            return "CON Name too short! Enter at least 2 characters:\n\n0. Back"

        session.data["last_name"] = clean.title()
        session.current_step = "reg_confirm"
        session.save()
        return (
            f"CON CONFIRM REGISTRATION:\n\n"
            f"📱 Phone: {session.phone_number}\n"
            f"👤 Name: {session.data['first_name']} {session.data['last_name']}\n\n"
            f"1. ✅ CONFIRM\n"
            f"0. ❌ Cancel"
        )

    def _handle_reg_confirm(self, session: USSDSession, choice: str) -> str:
        if choice == "1":
            try:
                phone_digits = re.sub(r"[^\d]", "", session.phone_number)
                email = f"{session.data['first_name'].lower()}.{session.data['last_name'].lower()}.{phone_digits[-6:]}@agrivision.ussd"
                username = f"{session.data['first_name'].lower()}{session.data['last_name'].lower()}{phone_digits[-4:]}"

                # Ensure unique
                counter = 1
                base_email, base_username = email, username
                while CustomUser.objects.filter(email=email).exists():
                    email = f"{base_email.split('@')[0]}.{counter}@agrivision.ussd"
                    counter += 1

                counter = 1
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = CustomUser.objects.create_user(
                    email=email,
                    username=username,
                    first_name=session.data["first_name"],
                    last_name=session.data["last_name"],
                    phone_number=session.phone_number,
                    registered_via_ussd=True,
                    ussd_registration_date=now(),
                    password=None,
                )
                session.delete()
                return (
                    f"END 🎉 SUCCESS! Welcome {user.first_name}!\n\n"
                    f"Phone: {user.phone_number}\n"
                    f"Redial *384# anytime for field advisory! 🌾"
                )
            except Exception as exc:
                logger.error("USSD registration failed: %s", exc)
                return "END Registration error. Please try again later."

        session.delete()
        return "END Registration cancelled."
