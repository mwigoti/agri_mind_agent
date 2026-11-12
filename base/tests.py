from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from base.services.agrimind_client import AgriMindClient
from base.services.ussd_service import USSDService
from base.test_model_lookup import ModelLookupFallbackTests

__all__ = [
    "ModelLookupFallbackTests",
    "AgriMindClientTests",
    "AgriMindAPITests",
    "USSDServiceTests",
]


class AgriMindClientTests(SimpleTestCase):
    def setUp(self):
        self.client = AgriMindClient(
            base_url="http://mock-agent:8001",
            api_token="test-token",
            reviewer_token="test-reviewer",
        )

    @patch("requests.get")
    def test_health_check_online(self, mock_get):
        mock_get.return_value.status_code = 200
        self.assertTrue(self.client.is_agent_online())
        mock_get.assert_called_with("http://mock-agent:8001/health", timeout=10)

    @patch("requests.get")
    def test_health_check_offline(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        self.assertFalse(self.client.is_agent_online())

    @patch("requests.post")
    def test_request_advisory_success(self, mock_post):
        mock_post.return_value.status_code = 202
        mock_post.return_value.json.return_value = {
            "thread_id": "thread-123",
            "execution_id": "exec-456",
            "status": "PENDING_APPROVAL",
            "advisory": "Irrigate field within 48h.",
        }
        res = self.client.request_advisory(plot_id=1)
        self.assertEqual(res["status"], "PENDING_APPROVAL")
        self.assertEqual(res["thread_id"], "thread-123")

    @patch("base.models.Field.objects.filter")
    @patch("requests.post")
    def test_request_advisory_fallback_uses_db_record(self, mock_post, mock_field_filter):
        mock_post.side_effect = Exception("Timeout")
        mock_field = MagicMock(id=42, name="North Plot")
        mock_field_filter.return_value.select_related.return_value.first.return_value = mock_field

        res = self.client.request_advisory(plot_id=42)

        self.assertEqual(res["status"], "DB_FALLBACK")
        self.assertIn("North Plot", res["advisory"])
        self.assertTrue(res["thread_id"].startswith("db-fallback-"))

    @patch("requests.post")
    def test_submit_decision(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "thread_id": "t-1",
            "status": "APPROVED",
            "decision": "APPROVE",
        }
        res = self.client.submit_decision("t-1", "APPROVE", reason="Looks good")
        self.assertEqual(res["status"], "APPROVED")

    @patch("requests.get")
    def test_get_prioritized_rankings(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "plots": [{"plot_id": "KE-001", "priority": "High"}]
        }
        rankings = self.client.get_prioritized_rankings()
        self.assertEqual(len(rankings), 1)
        self.assertEqual(rankings[0]["plot_id"], "KE-001")


class AgriMindAPITests(SimpleTestCase):
    def setUp(self):
        self.api = APIClient()

    @patch("base.services.agrimind_client.AgriMindClient.is_agent_online")
    def test_agrimind_status_endpoint(self, mock_online):
        mock_online.return_value = True
        response = self.api.get("/api/agent/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_online"], True)
        self.assertEqual(response.json()["status"], "connected")

    @patch("base.services.agrimind_client.AgriMindClient.request_advisory")
    def test_agrimind_advisory_endpoint(self, mock_adv):
        mock_adv.return_value = {
            "thread_id": "t-99",
            "status": "PENDING_APPROVAL",
            "advisory": "Scout for fall armyworm.",
        }
        response = self.api.post("/api/agent/advisory/5/", data={}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["thread_id"], "t-99")

    @patch("base.services.agrimind_client.AgriMindClient.submit_decision")
    def test_agrimind_decision_endpoint(self, mock_decide):
        mock_decide.return_value = {"status": "APPROVED", "decision": "APPROVE"}
        response = self.api.post(
            "/api/agent/decide/t-99/",
            data={"verdict": "APPROVE", "reason": "Verified on satellite"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "APPROVED")

    @patch("base.services.agrimind_client.AgriMindClient.get_prioritized_rankings")
    def test_agrimind_rankings_endpoint(self, mock_rank):
        mock_rank.return_value = [{"plot_id": "KE-001", "score": 90.0}]
        response = self.api.get("/api/agent/rankings/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["plots"]), 1)

    def test_chat_page_render(self):
        response = self.api.get("/chat/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AgriMind Assistant", response.content)

    @patch("base.views_chat._proxy_to_layer2", return_value=None)
    def test_chat_api_fallback(self, mock_proxy):
        response = self.api.post(
            "/api/agent/chat/",
            data={"message": "What is the weather forecast and rainfall status?"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("response", data)
        self.assertEqual(data["source"], "local_fallback")

    def test_chat_api_empty_message(self):
        response = self.api.post(
            "/api/agent/chat/",
            data={"message": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class USSDServiceTests(SimpleTestCase):
    def setUp(self):
        self.mock_agent = MagicMock()
        self.mock_sms = MagicMock()
        self.service = USSDService(agrimind_client=self.mock_agent, sms_service=self.mock_sms)

    def test_phone_number_cleaning(self):
        self.assertEqual(self.service.clean_phone_number("0712345678"), "+254712345678")
        self.assertEqual(self.service.clean_phone_number("254712345678"), "+254712345678")
        self.assertEqual(self.service.clean_phone_number("+254712345678"), "+254712345678")

    @patch("base.services.ussd_service.USSDSession.objects.get_or_create")
    @patch("base.services.ussd_service.CustomUser.objects.filter")
    def test_unregistered_farmer_welcome_menu(self, mock_user_filter, mock_session_get):
        mock_user_filter.return_value.first.return_value = None
        mock_session = MagicMock()
        mock_session.current_step = "start"
        mock_session.phone_number = "+254712345678"
        mock_session_get.return_value = (mock_session, False)

        resp = self.service.process(session_id="sess-001", phone_number="0712345678", text="")
        self.assertIn("Welcome to AgriVision", resp)
        self.assertIn("1. Register New Account", resp)
        self.assertEqual(mock_session.current_step, "reg_main")

    @patch("base.services.ussd_service.USSDSession.objects.get_or_create")
    @patch("base.services.ussd_service.CustomUser.objects.filter")
    def test_registered_farmer_welcome_menu(self, mock_user_filter, mock_session_get):
        mock_user = MagicMock(first_name="Wanjiku")
        mock_user_filter.return_value.first.return_value = mock_user
        mock_session = MagicMock()
        mock_session.current_step = "start"
        mock_session.phone_number = "+254712345678"
        mock_session_get.return_value = (mock_session, False)

        resp = self.service.process(session_id="sess-002", phone_number="0712345678", text="")
        self.assertIn("Welcome back, Wanjiku", resp)
        self.assertIn("1. Crop Health & Advisory", resp)
        self.assertIn("4. Send SMS Summary", resp)
        self.assertEqual(mock_session.current_step, "farmer_home")

    @patch("base.services.ussd_service.USSDSession.objects.get_or_create")
    @patch("base.services.ussd_service.CustomUser.objects.filter")
    def test_farmer_requests_sms_summary(self, mock_user_filter, mock_session_get):
        mock_user = MagicMock(first_name="Kiprono")
        mock_user_filter.return_value.first.return_value = mock_user
        mock_session = MagicMock()
        mock_session.current_step = "farmer_home"
        mock_session.phone_number = "+254712345678"
        mock_session_get.return_value = (mock_session, False)

        self.mock_sms.send_sms.return_value = (True, {"status": "Success"})
        resp = self.service.process(session_id="sess-003", phone_number="0712345678", text="4")

        self.assertIn("SMS summary sent", resp)
        self.mock_sms.send_sms.assert_called_once()

    @patch("base.services.ussd_service.USSDSession.objects.get_or_create")
    @patch("base.services.ussd_service.Field.objects.filter")
    def test_field_advisory_selection(self, mock_field_filter, mock_session_get):
        mock_field = MagicMock(id=10, name="Nakuru Maize Plot A")
        mock_field_filter.return_value.first.return_value = mock_field
        mock_session = MagicMock()
        mock_session.current_step = "select_field_advisory"
        mock_session.data = {"field_ids": [10]}
        mock_session.phone_number = "+254712345678"
        mock_session_get.return_value = (mock_session, False)

        self.mock_agent.request_advisory.return_value = {
            "status": "APPROVED",
            "selected_action": "HOLD",
        }

        resp = self.service.process(session_id="sess-004", phone_number="0712345678", text="1")
        self.assertIn("Nakuru Maize Plot", resp)
        self.assertIn("Action: HOLD", resp)
        self.assertIn("AgriMind AI Verified", resp)

    @patch("base.services.ussd_service.USSDService.process")
    def test_ussd_view_endpoint(self, mock_process):
        mock_process.return_value = "CON Welcome to AgriVision!"
        client = APIClient()
        response = client.post(
            "/ussd/callback/",
            data={"sessionId": "s-100", "phoneNumber": "+254712345678", "text": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "CON Welcome to AgriVision!")
