from decimal import Decimal
import smtplib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.serializers import code_key
from orders.models import Order, PaymentTransaction
from orders.services import DuplicatePendingOrder, complete_order_payment, create_order, expire_pending_orders
from payments.alipay import (
    canonicalize as alipay_canonicalize,
    sign_params as alipay_sign_params,
    verify_params as alipay_verify_params,
)
from payments.easypay import sign_params
from shop.models import CardSecret, Category, Product
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def make_rsa_key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


class ShopFixtureMixin:
    def setUp(self):
        self.category = Category.objects.create(name="AI 工具", slug="ai-tools")
        self.product = Product.objects.create(
            category=self.category,
            name="测试商品",
            price=Decimal("12.50"),
            is_active=True,
        )
        for value in ["CARD-001", "CARD-002"]:
            card = CardSecret(product=self.product)
            card.set_secret(value)
            card.save()


class OrderFlowTests(ShopFixtureMixin, TestCase):
    def test_create_order_reserves_stock(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        self.assertEqual(order.amount, Decimal("12.50"))
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(
            CardSecret.objects.filter(status=CardSecret.Status.RESERVED, reserved_order=order).count(),
            1,
        )

    def test_create_order_writes_business_log(self):
        with self.assertLogs("cardshop.orders", level="INFO") as logs:
            order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        output = "\n".join(logs.output)
        self.assertIn("event=order_created", output)
        self.assertIn(f"order_no={order.order_no}", output)
        self.assertNotIn("buyer@example.com", output)

    def test_create_order_rejects_insufficient_stock(self):
        create_order(product_id=self.product.id, quantity=2, contact="buyer@example.com")

        with self.assertRaises(ValidationError):
            create_order(product_id=self.product.id, quantity=1, contact="next@example.com")

    def test_same_user_same_product_pending_order_blocks_new_order(self):
        user = get_user_model().objects.create_user(
            username="repeat@example.com",
            email="repeat@example.com",
            password="Password123!",
        )
        first = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com", user=user)

        with self.assertRaises(DuplicatePendingOrder) as exc:
            create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com", user=user)

        self.assertEqual(exc.exception.order, first)
        self.assertEqual(Order.objects.filter(user=user, product=self.product).count(), 1)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.RESERVED).count(), 1)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 1)

    def test_guest_same_contact_same_product_pending_order_blocks_new_order(self):
        first = create_order(product_id=self.product.id, quantity=1, contact="Guest@Example.com")

        with self.assertRaises(DuplicatePendingOrder) as exc:
            create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        self.assertEqual(exc.exception.order, first)
        self.assertEqual(Order.objects.filter(user__isnull=True, product=self.product).count(), 1)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.RESERVED).count(), 1)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 1)

    def test_guest_duplicate_order_log_uses_contact_hash(self):
        create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        with self.assertLogs("cardshop.orders", level="INFO") as logs:
            with self.assertRaises(DuplicatePendingOrder):
                create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        output = "\n".join(logs.output)
        self.assertIn("event=order_duplicate_pending", output)
        self.assertIn("contact_hash=", output)
        self.assertNotIn("guest@example.com", output)

    def test_guest_different_contact_same_product_can_create_order(self):
        create_order(product_id=self.product.id, quantity=1, contact="one@example.com")
        create_order(product_id=self.product.id, quantity=1, contact="two@example.com")

        self.assertEqual(Order.objects.filter(user__isnull=True, product=self.product).count(), 2)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.RESERVED).count(), 2)

    def test_guest_same_contact_different_product_can_create_order(self):
        other_product = Product.objects.create(
            category=self.category,
            name="另一个商品",
            price=Decimal("6.00"),
            is_active=True,
        )
        card = CardSecret(product=other_product)
        card.set_secret("OTHER-001")
        card.save()

        create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")
        create_order(product_id=other_product.id, quantity=1, contact="guest@example.com")

        self.assertEqual(Order.objects.filter(user__isnull=True, contact="guest@example.com").count(), 2)

    def test_expired_order_releases_stock(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        Order.objects.filter(id=order.id).update(expires_at=timezone.now() - timezone.timedelta(minutes=1))

        count = expire_pending_orders()

        self.assertEqual(count, 1)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 2)

    def test_payment_success_delivers_cards(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        paid = complete_order_payment(order_no=order.order_no, amount=order.amount, provider="dev")

        self.assertEqual(paid.status, Order.Status.PAID)
        self.assertEqual(paid.delivery_items, ["CARD-001"])
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.SOLD).count(), 1)

    def test_payment_success_writes_business_log_without_delivery_items(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        with self.assertLogs("cardshop.payments", level="INFO") as logs:
            complete_order_payment(order_no=order.order_no, amount=order.amount, provider="dev", trade_no="T123")

        output = "\n".join(logs.output)
        self.assertIn("event=payment_completed", output)
        self.assertIn(f"order_no={order.order_no}", output)
        self.assertIn("trade_no=T123", output)
        self.assertNotIn("CARD-001", output)

    def test_duplicate_callback_is_idempotent(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        complete_order_payment(order_no=order.order_no, amount=order.amount, provider="dev")

        paid = complete_order_payment(order_no=order.order_no, amount=order.amount, provider="dev")

        self.assertEqual(paid.status, Order.Status.PAID)
        self.assertEqual(PaymentTransaction.objects.filter(status=PaymentTransaction.Status.IGNORED).count(), 1)

    def test_amount_mismatch_fails(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        with self.assertRaises(ValidationError):
            complete_order_payment(order_no=order.order_no, amount="1.00", provider="dev")

        self.assertEqual(PaymentTransaction.objects.filter(status=PaymentTransaction.Status.FAILED).count(), 1)


class ApiFlowTests(ShopFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="buyer@example.com",
            email="buyer@example.com",
            password="Password123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @override_settings(DEBUG=True)
    def test_order_api_hides_delivery_until_paid(self):
        response = self.client.post(
            "/api/orders",
            {"product_id": self.product.id, "quantity": 1, "contact": "buyer@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        order_no = response.data["order_no"]

        query = self.client.get("/api/orders/query", {"keyword": "buyer@example.com"})
        self.assertEqual(query.data["results"][0]["delivery_items"], [])

        complete = self.client.post("/api/payments/dev/complete", {"order_no": order_no}, format="json")
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.data["delivery_items"], ["CARD-001"])

    def test_guest_user_can_create_order(self):
        client = APIClient()

        response = client.post(
            "/api/orders",
            {"product_id": self.product.id, "quantity": 1, "contact": "Guest@Example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(order_no=response.data["order_no"])
        self.assertIsNone(order.user_id)
        self.assertEqual(order.contact, "guest@example.com")
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.RESERVED).count(), 1)

    def test_guest_duplicate_pending_order_returns_existing_order(self):
        client = APIClient()
        existing = create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        response = client.post(
            "/api/orders",
            {"product_id": self.product.id, "quantity": 1, "contact": "GUEST@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["existing_order_no"], existing.order_no)
        self.assertEqual(Order.objects.filter(user__isnull=True, product=self.product).count(), 1)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.RESERVED).count(), 1)

    def test_duplicate_pending_order_returns_existing_order(self):
        existing = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com", user=self.user)

        response = self.client.post(
            "/api/orders",
            {"product_id": self.product.id, "quantity": 1, "contact": "buyer@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["existing_order_no"], existing.order_no)
        self.assertEqual(Order.objects.filter(user=self.user, product=self.product).count(), 1)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.RESERVED).count(), 1)

    def test_order_query_only_returns_current_user_orders(self):
        other_user = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Password123!",
        )
        create_order(product_id=self.product.id, quantity=1, contact="same@example.com", user=self.user)
        create_order(product_id=self.product.id, quantity=1, contact="same@example.com", user=other_user)

        response = self.client.get("/api/orders/query", {"keyword": "same@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_guest_query_requires_order_no_and_matching_contact(self):
        client = APIClient()
        order = create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        missing = client.get("/api/orders/query", {"order_no": order.order_no})
        wrong = client.get("/api/orders/query", {"order_no": order.order_no, "contact": "wrong@example.com"})
        matched = client.get("/api/orders/query", {"order_no": order.order_no, "contact": "GUEST@example.com"})

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(wrong.status_code, 200)
        self.assertEqual(wrong.data["results"], [])
        self.assertEqual(matched.status_code, 200)
        self.assertEqual(matched.data["results"][0]["order_no"], order.order_no)

    @override_settings(DEBUG=True)
    def test_dev_payment_requires_owner(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com", user=self.user)
        other_user = get_user_model().objects.create_user(
            username="other-pay@example.com",
            email="other-pay@example.com",
            password="Password123!",
        )
        client = APIClient()
        client.force_authenticate(other_user)

        response = client.post("/api/payments/dev/complete", {"order_no": order.order_no}, format="json")

        self.assertEqual(response.status_code, 400)

    @override_settings(PAYMENT_PROVIDER="dev", DEBUG=True)
    def test_pending_order_can_request_payment_again(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com", user=self.user)

        response = self.client.post(f"/api/orders/{order.order_no}/payment", format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["order_no"], order.order_no)
        self.assertEqual(response.data["payment"]["mode"], "dev")

    @override_settings(PAYMENT_PROVIDER="dev", DEBUG=True)
    def test_user_cannot_request_other_users_payment(self):
        other_user = get_user_model().objects.create_user(
            username="other-order@example.com",
            email="other-order@example.com",
            password="Password123!",
        )
        order = create_order(product_id=self.product.id, quantity=1, contact="other@example.com", user=other_user)

        response = self.client.post(f"/api/orders/{order.order_no}/payment", format="json")

        self.assertEqual(response.status_code, 404)

    @override_settings(PAYMENT_PROVIDER="dev", DEBUG=True)
    def test_guest_can_request_payment_again_with_matching_contact(self):
        client = APIClient()
        order = create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        wrong = client.post(
            f"/api/orders/{order.order_no}/payment",
            {"contact": "wrong@example.com"},
            format="json",
        )
        matched = client.post(
            f"/api/orders/{order.order_no}/payment",
            {"contact": "GUEST@example.com"},
            format="json",
        )

        self.assertEqual(wrong.status_code, 404)
        self.assertEqual(matched.status_code, 200)
        self.assertEqual(matched.data["payment"]["mode"], "dev")

    @override_settings(DEBUG=True)
    def test_guest_dev_payment_requires_matching_contact(self):
        client = APIClient()
        order = create_order(product_id=self.product.id, quantity=1, contact="guest@example.com")

        wrong = client.post(
            "/api/payments/dev/complete",
            {"order_no": order.order_no, "contact": "wrong@example.com"},
            format="json",
        )
        matched = client.post(
            "/api/payments/dev/complete",
            {"order_no": order.order_no, "contact": "GUEST@example.com"},
            format="json",
        )

        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(matched.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @override_settings(PAYMENT_PROVIDER="dev", DEBUG=True)
    def test_expired_order_cannot_request_payment_again(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com", user=self.user)
        Order.objects.filter(id=order.id).update(expires_at=timezone.now() - timezone.timedelta(minutes=1))

        response = self.client.post(f"/api/orders/{order.order_no}/payment", format="json")

        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)

    @override_settings(DEBUG=False)
    def test_dev_payment_disabled_in_production(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com", user=self.user)

        response = self.client.post("/api/payments/dev/complete", {"order_no": order.order_no}, format="json")

        self.assertEqual(response.status_code, 403)

    @override_settings(EASYPAY_KEY="secret")
    def test_easypay_notify_verifies_signature(self):
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        payload = {
            "out_trade_no": order.order_no,
            "trade_no": "T123",
            "money": str(order.amount),
            "trade_status": "TRADE_SUCCESS",
        }
        payload["sign"] = sign_params(payload, key="secret")
        payload["sign_type"] = "MD5"

        response = self.client.post("/api/payments/easypay/notify", payload)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

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

    def test_alipay_sign_and_verify(self):
        private_pem, public_pem = make_rsa_key_pair()
        payload = {"app_id": "app_123", "out_trade_no": "O123", "total_amount": "12.50"}
        payload["sign"] = alipay_sign_params(payload, private_key=private_pem)
        payload["sign_type"] = "RSA2"

        self.assertTrue(alipay_verify_params(payload, public_key=public_pem))
        payload["total_amount"] = "1.00"
        self.assertFalse(alipay_verify_params(payload, public_key=public_pem))

    def test_alipay_canonicalize_keeps_sign_type(self):
        payload = {
            "app_id": "app_123",
            "method": "alipay.trade.page.pay",
            "sign": "ignored",
            "sign_type": "RSA2",
            "timestamp": "2026-04-28 14:55:48",
        }

        sign_content = alipay_canonicalize(payload)

        self.assertIn("sign_type=RSA2", sign_content)
        self.assertNotIn("sign=ignored", sign_content)

    def test_alipay_order_response_returns_redirect_url(self):
        private_pem, public_pem = make_rsa_key_pair()
        with override_settings(
            PAYMENT_PROVIDER="alipay",
            ALIPAY_APP_ID="app_123",
            ALIPAY_APP_PRIVATE_KEY=private_pem,
            ALIPAY_PUBLIC_KEY=public_pem,
            ALIPAY_GATEWAY_URL="https://openapi-sandbox.dl.alipaydev.com/gateway.do",
        ):
            response = self.client.post(
                "/api/orders",
                {"product_id": self.product.id, "quantity": 1, "contact": "buyer@example.com"},
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["payment"]["mode"], "alipay")
        self.assertIn("redirect_url", response.data["payment"])
        self.assertIn("sign=", response.data["payment"]["redirect_url"])

    def test_alipay_notify_verifies_signature_and_delivers(self):
        private_pem, public_pem = make_rsa_key_pair()
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com", user=self.user)
        payload = {
            "app_id": "app_123",
            "out_trade_no": order.order_no,
            "trade_no": "ALI202604280001",
            "total_amount": str(order.amount),
            "trade_status": "TRADE_SUCCESS",
        }
        payload["sign"] = alipay_sign_params(payload, private_key=private_pem)
        payload["sign_type"] = "RSA2"

        with override_settings(ALIPAY_APP_ID="app_123", ALIPAY_PUBLIC_KEY=public_pem):
            response = self.client.post("/api/payments/alipay/notify", payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"success")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.delivery_items, ["CARD-001"])

    def test_alipay_notify_rejects_invalid_signature(self):
        _private_pem, public_pem = make_rsa_key_pair()
        payload = {
            "app_id": "app_123",
            "out_trade_no": "O123",
            "trade_no": "ALI202604280002",
            "total_amount": "12.50",
            "trade_status": "TRADE_SUCCESS",
            "sign": "invalid",
            "sign_type": "RSA2",
        }

        with override_settings(ALIPAY_APP_ID="app_123", ALIPAY_PUBLIC_KEY=public_pem):
            response = self.client.post("/api/payments/alipay/notify", payload)

        self.assertEqual(response.status_code, 400)

    def test_email_register_login_and_reset_flow(self):
        email = "new@example.com"
        code_response = self.client.post("/api/auth/email-code", {"email": email, "purpose": "register"}, format="json")
        self.assertEqual(code_response.status_code, 200)
        code = cache.get(code_key("register", email))

        register = self.client.post(
            "/api/auth/register",
            {"email": email, "password": "Password123!", "code": code},
            format="json",
        )
        self.assertEqual(register.status_code, 201)
        self.assertIn("access", register.data["tokens"])
        refresh = self.client.post(
            "/api/auth/token/refresh",
            {"refresh": register.data["tokens"]["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertIn("access", refresh.data)

        login = self.client.post("/api/auth/login", {"email": email, "password": "Password123!"}, format="json")
        self.assertEqual(login.status_code, 200)

        reset_code_response = self.client.post(
            "/api/auth/email-code",
            {"email": email, "purpose": "reset"},
            format="json",
        )
        self.assertEqual(reset_code_response.status_code, 200)
        reset_code = cache.get(code_key("reset", email))
        reset = self.client.post(
            "/api/auth/reset-password",
            {"email": email, "password": "Password456!", "code": reset_code},
            format="json",
        )
        self.assertEqual(reset.status_code, 200)

    def test_email_code_returns_readable_error_when_smtp_fails(self):
        email = "smtp-fail@example.com"
        with patch("accounts.serializers.send_mail", side_effect=smtplib.SMTPException("smtp down")):
            response = self.client.post(
                "/api/auth/email-code",
                {"email": email, "purpose": "register"},
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("验证码发送失败", str(response.data))
        self.assertIsNone(cache.get(code_key("register", email)))
