from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView


class ErrorView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        raise RuntimeError("boom")


class OkView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"ok": True})


urlpatterns = [
    path("logging-error", ErrorView.as_view()),
    path("logging-ok", OkView.as_view()),
]


@override_settings(ROOT_URLCONF=__name__)
class RequestLoggingMiddlewareTests(TestCase):
    def setUp(self):
        self.client.raise_request_exception = False

    def test_generates_request_id_response_header(self):
        response = self.client.get("/logging-ok")

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response["X-Request-ID"], r"^[a-f0-9-]{36}$")

    def test_preserves_valid_request_id(self):
        response = self.client.get("/logging-ok", HTTP_X_REQUEST_ID="support-123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Request-ID"], "support-123")

    def test_replaces_unsafe_request_id(self):
        response = self.client.get("/logging-ok", HTTP_X_REQUEST_ID="../bad\nid")

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response["X-Request-ID"], "../bad\nid")
        self.assertRegex(response["X-Request-ID"], r"^[a-f0-9-]{36}$")

    def test_request_log_contains_status_and_duration(self):
        with self.assertLogs("cardshop.request", level="INFO") as logs:
            response = self.client.get("/logging-ok", HTTP_X_REQUEST_ID="support-234")

        self.assertEqual(response.status_code, 200)
        output = "\n".join(logs.output)
        self.assertIn("event=http_request", output)
        self.assertIn("request_id=support-234", output)
        self.assertIn("status_code=200", output)
        self.assertIn("duration_ms=", output)

    def test_exception_log_contains_request_id(self):
        with self.assertLogs("cardshop.request", level="ERROR") as logs:
            response = self.client.get("/logging-error", HTTP_X_REQUEST_ID="support-456")

        self.assertEqual(response.status_code, 500)
        self.assertIn("request_id=support-456", "\n".join(logs.output))


class HealthRequestLoggingTests(TestCase):
    def test_health_check_does_not_emit_info_request_log(self):
        with patch("config.middleware.request_logger.info") as info_log:
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        info_log.assert_not_called()
