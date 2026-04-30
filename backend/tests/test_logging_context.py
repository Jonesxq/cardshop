from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from config.logging_context import (
    RequestContextFilter,
    clear_request_context,
    contact_hash,
    get_request_id,
    sanitize_payload,
    set_request_context,
)


class LoggingContextTests(SimpleTestCase):
    def tearDown(self):
        clear_request_context()

    def test_request_context_filter_adds_context_fields(self):
        set_request_context(request_id="req-123", user_id="42", user_email="user@example.com", client_ip="127.0.0.1")
        record = type("Record", (), {})()

        self.assertTrue(RequestContextFilter().filter(record))

        self.assertEqual(record.request_id, "req-123")
        self.assertEqual(record.user_id, "42")
        self.assertEqual(record.user_email, "user@example.com")
        self.assertEqual(record.client_ip, "127.0.0.1")
        self.assertEqual(get_request_id(), "req-123")

    def test_context_filter_uses_dash_without_request(self):
        record = type("Record", (), {})()

        RequestContextFilter().filter(record)

        self.assertEqual(record.request_id, "-")
        self.assertEqual(record.user_id, "-")
        self.assertEqual(record.user_email, "-")
        self.assertEqual(record.client_ip, "-")

    def test_sanitize_payload_masks_nested_sensitive_values(self):
        payload = {
            "out_trade_no": "O123",
            "password": "secret-password",
            "buyer_email": "buyer@example.com",
            "nested": {"token": "abc", "amount": "12.50"},
            "items": [{"card_secret": "CARD-001"}],
        }

        sanitized = sanitize_payload(payload)

        self.assertEqual(sanitized["out_trade_no"], "O123")
        self.assertEqual(sanitized["password"], "***")
        self.assertEqual(sanitized["buyer_email"], "***")
        self.assertEqual(sanitized["nested"]["token"], "***")
        self.assertEqual(sanitized["nested"]["amount"], "12.50")
        self.assertEqual(sanitized["items"][0]["card_secret"], "***")

    @override_settings(SECRET_KEY="test-secret")
    def test_contact_hash_is_stable_and_does_not_expose_contact(self):
        first = contact_hash("Guest@Example.com")
        second = contact_hash("guest@example.com")

        self.assertEqual(first, second)
        self.assertNotIn("guest", first)
        self.assertEqual(len(first), 16)


class LoggingSettingsTests(SimpleTestCase):
    def test_logging_config_has_expected_handlers_and_loggers(self):
        self.assertIn("console", settings.LOGGING["handlers"])
        self.assertIn("app_file", settings.LOGGING["handlers"])
        self.assertIn("error_file", settings.LOGGING["handlers"])
        self.assertIn("security_file", settings.LOGGING["handlers"])
        self.assertIn("cardshop.request", settings.LOGGING["loggers"])
        self.assertIn("cardshop.security", settings.LOGGING["loggers"])

    def test_log_dir_defaults_under_backend(self):
        self.assertEqual(Path(settings.LOG_DIR).name, "logs")
