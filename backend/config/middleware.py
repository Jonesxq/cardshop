import logging
import re
import time
import uuid

from django.conf import settings

from .logging_context import clear_request_context, set_request_context


REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_REQUEST_ID_HEADER = "X-Request-ID"
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")

request_logger = logging.getLogger("cardshop.request")
security_logger = logging.getLogger("cardshop.security")


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def get_request_id(request):
    candidate = request.META.get(REQUEST_ID_HEADER, "")
    if candidate and SAFE_REQUEST_ID.match(candidate):
        return candidate
    if candidate:
        security_logger.warning(
            "event=unsafe_request_id outcome=replaced client_ip=%s",
            get_client_ip(request),
        )
    return str(uuid.uuid4())


def get_response_size(response):
    content = getattr(response, "content", None)
    return len(content) if content is not None else "-"


def should_skip_request_info(path):
    return path == "/api/health"


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.monotonic()
        request_id = get_request_id(request)
        client_ip = get_client_ip(request)
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            user_id = getattr(user, "id", "")
            user_email = getattr(user, "email", "")
        else:
            user_id = ""
            user_email = ""
        set_request_context(
            request_id=request_id,
            user_id=user_id,
            user_email=user_email,
            client_ip=client_ip,
        )

        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            request_logger.exception(
                "event=http_exception request_id=%s method=%s path=%s duration_ms=%s client_ip=%s",
                request_id,
                request.method,
                request.path,
                duration_ms,
                client_ip,
            )
            raise

        duration_ms = int((time.monotonic() - started_at) * 1000)
        response[RESPONSE_REQUEST_ID_HEADER] = request_id
        status_code = getattr(response, "status_code", 0)
        if not should_skip_request_info(request.path):
            log_method = request_logger.warning if duration_ms >= settings.SLOW_REQUEST_MS else request_logger.info
            if status_code >= 500:
                log_method = request_logger.error
            log_method(
                "event=http_request request_id=%s method=%s path=%s status_code=%s duration_ms=%s user_id=%s "
                "client_ip=%s response_size=%s",
                request_id,
                request.method,
                request.path,
                status_code,
                duration_ms,
                user_id or "-",
                client_ip or "-",
                get_response_size(response),
            )
        clear_request_context()
        return response
