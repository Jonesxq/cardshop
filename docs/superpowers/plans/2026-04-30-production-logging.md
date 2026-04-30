# 生产日志 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Django 后端增加生产可用的请求日志、异常日志、业务事件日志、标准输出和文件日志。

**Architecture:** 在 `config` 内新增日志上下文、日志工具和请求中间件，让所有 logger 自动带 `request_id`、用户和 IP。业务模块只通过标准 `logging.getLogger(...)` 写安全字段，Django `settings.LOGGING` 统一决定 stdout、文件和安全日志输出。

**Tech Stack:** Django 5.2、Python 标准库 `logging`、`contextvars`、`RotatingFileHandler`、pytest-django、DRF test client、Docker Compose。

---

## 文件结构

- 新建 `backend/config/logging_context.py`：保存请求上下文、注入 logging record、脱敏 payload、生成游客联系方式哈希。
- 新建 `backend/config/middleware.py`：生成或继承 `X-Request-ID`，记录请求完成、慢请求和异常。
- 新建 `backend/tests/test_logging_context.py`：测试上下文、脱敏、联系方式哈希。
- 新建 `backend/tests/test_request_logging.py`：测试请求 ID、中间件请求日志和健康检查跳过 info 日志。
- 修改 `backend/config/settings.py`：注册中间件、日志环境变量、`LOGGING` 配置和文件 handler。
- 修改 `backend/orders/services.py`：补订单创建、重复订单、库存不足、过期释放、支付完成/失败日志。
- 修改 `backend/payments/gateway.py`：补支付响应创建日志。
- 修改 `backend/payments/views.py`：补支付回调验签失败、状态忽略、回调处理失败日志。
- 修改 `backend/tests/test_order_flow.py`：补订单与支付业务事件日志测试。
- 修改 `.env.example`、`.env.production.example`：补日志配置变量。
- 修改 `docker-compose.yml`：挂载 `backend_logs` volume 到 `/app/logs`。
- 修改 `README.md`：补日志查看和 `X-Request-ID` 排错说明。

## Task 1: 日志上下文和脱敏工具

**Files:**
- Create: `backend/config/logging_context.py`
- Test: `backend/tests/test_logging_context.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; uv run pytest tests/test_logging_context.py -q`

Expected: `ModuleNotFoundError: No module named 'config.logging_context'`

- [ ] **Step 3: 实现工具模块**

实现 `config.logging_context`，提供：

```python
set_request_context(request_id="", user_id="", user_email="", client_ip="")
clear_request_context()
get_request_id()
RequestContextFilter
sanitize_payload(value)
contact_hash(contact)
```

脱敏键使用大小写不敏感的包含匹配，覆盖 `password`、`token`、`secret`、`key`、`sign`、`authorization`、`cookie`、`code`、`card`、`private`、`email`、`mobile`、`phone`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend; uv run pytest tests/test_logging_context.py -q`

Expected: `4 passed`

## Task 2: 请求日志中间件

**Files:**
- Create: `backend/config/middleware.py`
- Modify: `backend/config/settings.py`
- Test: `backend/tests/test_request_logging.py`

- [ ] **Step 1: 写失败测试**

```python
import logging

from django.test import TestCase, override_settings
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView


class ErrorView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        raise RuntimeError("boom")


urlpatterns = [
    path("logging-error", ErrorView.as_view()),
]


@override_settings(ROOT_URLCONF=__name__)
class RequestLoggingMiddlewareTests(TestCase):
    def test_generates_request_id_response_header(self):
        response = self.client.get("/logging-error")
        self.assertEqual(response.status_code, 500)
        self.assertRegex(response["X-Request-ID"], r"^[a-f0-9-]{36}$")

    def test_preserves_valid_request_id(self):
        response = self.client.get("/logging-error", HTTP_X_REQUEST_ID="support-123")
        self.assertEqual(response["X-Request-ID"], "support-123")

    def test_replaces_unsafe_request_id(self):
        response = self.client.get("/logging-error", HTTP_X_REQUEST_ID="../bad\nid")
        self.assertNotEqual(response["X-Request-ID"], "../bad\nid")
        self.assertRegex(response["X-Request-ID"], r"^[a-f0-9-]{36}$")

    def test_exception_log_contains_request_id(self):
        with self.assertLogs("cardshop.request", level="ERROR") as logs:
            response = self.client.get("/logging-error", HTTP_X_REQUEST_ID="support-456")

        self.assertEqual(response.status_code, 500)
        self.assertIn("request_id=support-456", "\n".join(logs.output))


class HealthRequestLoggingTests(TestCase):
    def test_health_check_does_not_emit_info_request_log(self):
        logger = logging.getLogger("cardshop.request")
        with self.assertLogs("cardshop.request", level="DEBUG") as logs:
            self.client.get("/api/health")

        self.assertNotIn("event=http_request", "\n".join(logs.output))
        self.assertEqual(logger.name, "cardshop.request")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; uv run pytest tests/test_request_logging.py -q`

Expected: middleware 尚未注册，断言缺少 `X-Request-ID` 或日志失败。

- [ ] **Step 3: 实现中间件并注册**

在 `backend/config/middleware.py` 实现：

```python
class RequestLoggingMiddleware:
    def __init__(self, get_response): ...
    def __call__(self, request): ...
```

中间件要生成安全 request ID、设置上下文、响应写入 `X-Request-ID`、跳过 `/api/health` info 日志、异常时 `logger.exception(...)`。在 `settings.MIDDLEWARE` 中放到 `AuthenticationMiddleware` 后面，这样能拿到 `request.user`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend; uv run pytest tests/test_request_logging.py -q`

Expected: `5 passed`

## Task 3: Django 日志配置、部署配置和文档

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `.env.example`
- Modify: `.env.production.example`
- Modify: `docker-compose.yml`
- Modify: `README.md`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_logging_context.py` 追加：

```python
from pathlib import Path
from django.conf import settings


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; uv run pytest tests/test_logging_context.py::LoggingSettingsTests -q`

Expected: `settings.LOGGING` 缺少对应 handlers 或 loggers。

- [ ] **Step 3: 实现配置与文档**

在 `settings.py` 添加 `LOG_LEVEL`、`LOG_TO_FILE`、`LOG_DIR`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT`、`SLOW_REQUEST_MS`，创建日志目录，配置 console、app_file、error_file、security_file handlers。

`.env.example` 和 `.env.production.example` 增加同名变量。`docker-compose.yml` 增加 `backend_logs:/app/logs` 和 `backend_logs:` volume。`README.md` 增加日志查看命令。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend; uv run pytest tests/test_logging_context.py::LoggingSettingsTests -q`

Expected: `2 passed`

## Task 4: 订单与支付业务事件日志

**Files:**
- Modify: `backend/orders/services.py`
- Modify: `backend/payments/gateway.py`
- Modify: `backend/payments/views.py`
- Modify: `backend/tests/test_order_flow.py`

- [ ] **Step 1: 写失败测试**

在 `OrderFlowTests` 和 `ApiFlowTests` 中追加测试：

```python
    def test_create_order_writes_business_log(self):
        with self.assertLogs("cardshop.orders", level="INFO") as logs:
            order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        output = "\n".join(logs.output)
        self.assertIn("event=order_created", output)
        self.assertIn(f"order_no={order.order_no}", output)
        self.assertNotIn("buyer@example.com", output)

    def test_guest_duplicate_order_log_uses_contact_hash(self):
        create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        with self.assertLogs("cardshop.orders", level="INFO") as logs:
            with self.assertRaises(DuplicatePendingOrder):
                create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        output = "\n".join(logs.output)
        self.assertIn("event=order_duplicate_pending", output)
        self.assertIn("contact_hash=", output)
        self.assertNotIn("guest@example.com", output)

    def test_payment_success_writes_business_log_without_delivery_items(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        with self.assertLogs("cardshop.payments", level="INFO") as logs:
            complete_order_payment(order_no=order.order_no, amount=order.amount, provider="dev", trade_no="T123")

        output = "\n".join(logs.output)
        self.assertIn("event=payment_completed", output)
        self.assertIn(f"order_no={order.order_no}", output)
        self.assertIn("trade_no=T123", output)
        self.assertNotIn("CARD-001", output)
```

在 `ApiFlowTests` 追加：

```python
    @override_settings(EASYPAY_KEY="secret")
    def test_invalid_easypay_signature_writes_security_log(self):
        payload = {
            "out_trade_no": "O123",
            "trade_no": "T123",
            "money": "12.50",
            "trade_status": "TRADE_SUCCESS",
            "sign": "bad",
        }

        with self.assertLogs("cardshop.security", level="WARNING") as logs:
            response = self.client.post("/api/payments/easypay/notify", payload)

        self.assertEqual(response.status_code, 400)
        output = "\n".join(logs.output)
        self.assertIn("event=payment_notify_invalid_signature", output)
        self.assertIn("provider=easypay", output)
        self.assertNotIn("sign=bad", output)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; uv run pytest tests/test_order_flow.py -q`

Expected: 新增日志断言失败。

- [ ] **Step 3: 实现业务日志**

在订单服务和支付视图中使用：

```python
orders_logger = logging.getLogger("cardshop.orders")
payments_logger = logging.getLogger("cardshop.payments")
notify_logger = logging.getLogger("cardshop.payments.notify")
security_logger = logging.getLogger("cardshop.security")
```

只记录安全字段，不记录联系方式原文、卡密明文、验证码、token、签名或完整 payload。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend; uv run pytest tests/test_order_flow.py -q`

Expected: 订单流测试全部通过。

## Task 5: 全量验证

**Files:**
- Verify only.

- [ ] **Step 1: 运行完整后端测试**

Run: `cd backend; uv run pytest -q`

Expected: 全部测试通过。

- [ ] **Step 2: 运行 Django system check**

Run: `cd backend; uv run python manage.py check`

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: 检查 git diff**

Run: `git diff --stat`

Expected: 只包含日志实现、测试、配置和文档相关文件。

