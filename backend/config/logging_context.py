import hashlib
import hmac
from contextvars import ContextVar

from django.conf import settings


_request_id = ContextVar("request_id", default="-")
_user_id = ContextVar("user_id", default="-")
_user_email = ContextVar("user_email", default="-")
_client_ip = ContextVar("client_ip", default="-")

SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "key",
    "sign",
    "authorization",
    "cookie",
    "code",
    "card",
    "private",
    "email",
    "mobile",
    "phone",
)


def _clean_context_value(value):
    if value is None or value == "":
        return "-"
    return str(value)


def set_request_context(*, request_id="", user_id="", user_email="", client_ip=""):
    _request_id.set(_clean_context_value(request_id))
    _user_id.set(_clean_context_value(user_id))
    _user_email.set(_clean_context_value(user_email))
    _client_ip.set(_clean_context_value(client_ip))


def clear_request_context():
    set_request_context()


def get_request_id():
    return _request_id.get()


class RequestContextFilter:
    def filter(self, record):
        record.request_id = _request_id.get()
        record.user_id = _user_id.get()
        record.user_email = _user_email.get()
        record.client_ip = _client_ip.get()
        return True


def _is_sensitive_key(key):
    lowered = str(key).lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def sanitize_payload(value):
    if isinstance(value, dict):
        return {
            key: "***" if _is_sensitive_key(key) else sanitize_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_payload(item) for item in value]
    return value


def contact_hash(contact):
    normalized = (contact or "").strip().lower()
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:16]
