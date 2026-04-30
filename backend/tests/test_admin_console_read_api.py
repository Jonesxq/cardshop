from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from admin_console.models import AdminProfile
from admin_console.permissions import has_admin_permission
from admin_console.serializers import PaymentAdminSerializer
from orders.models import Order, PaymentTransaction
from shop.models import Announcement, CardSecret, Category, Product, SiteConfig


class AdminConsoleReadApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.operator = User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.operator, role=AdminProfile.Role.OPERATOR)
        self.finance = User.objects.create_user(
            username="finance@example.com",
            email="finance@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.finance, role=AdminProfile.Role.FINANCE)
        self.client = APIClient()
        self.category = Category.objects.create(name="AI Tools", slug="ai-tools")
        self.product = Product.objects.create(
            category=self.category,
            name="Codex Card",
            price=Decimal("99.00"),
            is_active=True,
        )
        card = CardSecret(product=self.product)
        card.set_secret("CARD-001")
        card.save()
        self.order = Order.objects.create(
            order_no="O202604300001",
            product=self.product,
            quantity=1,
            contact="buyer@example.com",
            amount=Decimal("99.00"),
            status=Order.Status.PAID,
            expires_at=timezone.now() + timezone.timedelta(minutes=15),
            paid_at=timezone.now(),
            delivered_at=timezone.now(),
            delivery_items=["CARD-001"],
        )
        PaymentTransaction.objects.create(
            order=self.order,
            provider="alipay",
            trade_no="ALI-1",
            out_trade_no=self.order.order_no,
            amount=Decimal("99.00"),
            status=PaymentTransaction.Status.SUCCESS,
            raw_payload={"buyer_email": "secret@example.com", "trade_no": "ALI-1"},
        )
        Announcement.objects.create(title="Notice", content="Content", is_active=True)
        SiteConfig.objects.create(key="site_name", label="Site name", value="AI Shop")

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_dashboard_returns_metrics_and_task_lists(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["today_order_count"], 1)
        self.assertEqual(response.data["summary"]["today_paid_amount"], "99.00")
        self.assertEqual(response.data["summary"]["pending_order_count"], 0)
        self.assertEqual(response.data["summary"]["low_stock_product_count"], 1)
        self.assertEqual(response.data["summary"]["abnormal_payment_count"], 0)
        self.assertEqual(response.data["top_products"][0]["name"], "Codex Card")

    def test_dashboard_product_metrics_do_not_multiply_card_and_order_joins(self):
        for index in range(2):
            card = CardSecret(product=self.product)
            card.set_secret(f"CARD-00{index + 2}")
            card.save()
        Order.objects.create(
            order_no="O202604300002",
            product=self.product,
            quantity=1,
            contact="buyer-2@example.com",
            amount=Decimal("50.00"),
            status=Order.Status.PAID,
            expires_at=timezone.now() + timezone.timedelta(minutes=15),
            paid_at=timezone.now(),
        )
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["top_products"][0]["paid_order_count"], 2)
        self.assertEqual(response.data["top_products"][0]["paid_amount"], "149.00")
        self.assertEqual(response.data["low_stock_products"][0]["available"], 3)
        self.assertEqual(response.data["summary"]["low_stock_product_count"], 1)

    def test_products_list_includes_stock_count(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["name"], "Codex Card")
        self.assertEqual(response.data["results"][0]["stock"]["available"], 1)

    def test_products_list_uses_grouped_stock_counts(self):
        for index in range(3):
            product = Product.objects.create(
                category=self.category,
                name=f"Extra Card {index}",
                price=Decimal("19.00"),
                is_active=True,
            )
            card = CardSecret(product=product)
            card.set_secret(f"EXTRA-{index}")
            card.save()
        self.authenticate(self.operator)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/admin-console/products")

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 4)

    def test_products_filter_by_keyword(self):
        Product.objects.create(
            category=self.category,
            name="Other Card",
            price=Decimal("9.00"),
            is_active=True,
        )
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/products", {"keyword": "Codex"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Codex Card")

    def test_operator_can_create_category_and_product(self):
        self.authenticate(self.operator)

        category_response = self.client.post(
            "/api/admin-console/categories",
            {"name": "Agents", "slug": "agents", "sort_order": 2, "is_active": True},
            format="json",
        )
        product_response = self.client.post(
            "/api/admin-console/products",
            {
                "category": category_response.data["id"],
                "name": "Agent Card",
                "description": "Useful agent credits",
                "price": "39.00",
                "image_url": "",
                "is_active": True,
                "sort_order": 3,
            },
            format="json",
        )

        self.assertEqual(category_response.status_code, 201)
        self.assertEqual(product_response.status_code, 201)
        self.assertEqual(product_response.data["category_name"], "Agents")

    def test_operator_can_patch_product_status(self):
        self.authenticate(self.operator)

        response = self.client.patch(
            f"/api/admin-console/products/{self.product.id}",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.is_active, False)

    def test_finance_cannot_list_products(self):
        self.authenticate(self.finance)

        response = self.client.get("/api/admin-console/products")

        self.assertEqual(response.status_code, 403)

    def test_cards_list_does_not_expose_plain_or_encrypted_secret(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/cards")

        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.data["results"][0])
        self.assertNotIn("encrypted_secret", response.data["results"][0])
        self.assertNotIn("CARD-001", str(response.data))

    def test_cards_filter_by_product_and_status(self):
        reserved_card = CardSecret(product=self.product, status=CardSecret.Status.RESERVED)
        reserved_card.set_secret("CARD-RESERVED")
        reserved_card.save()
        other_product = Product.objects.create(
            category=self.category,
            name="Other Card",
            price=Decimal("9.00"),
            is_active=True,
        )
        other_card = CardSecret(product=other_product, status=CardSecret.Status.RESERVED)
        other_card.set_secret("OTHER-RESERVED")
        other_card.save()
        self.authenticate(self.operator)

        response = self.client.get(
            "/api/admin-console/cards",
            {"product_id": self.product.id, "status": CardSecret.Status.RESERVED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], reserved_card.id)

    def test_operator_cannot_list_payment_transactions(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/payments")

        self.assertEqual(response.status_code, 403)

    def test_finance_can_list_payment_transactions_with_raw_payload(self):
        self.assertEqual(has_admin_permission(self.finance, "can_view_sensitive_payload"), True)
        self.authenticate(self.finance)

        response = self.client.get("/api/admin-console/payments")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["raw_payload"]["buyer_email"], "secret@example.com")

    def test_orders_filter_by_status(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/orders", {"status": "paid"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["order_no"], "O202604300001")

    def test_order_detail_returns_delivery_items_for_operator(self):
        self.authenticate(self.operator)

        response = self.client.get(f"/api/admin-console/orders/{self.order.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["delivery_items"], ["CARD-001"])

    def test_payment_detail_returns_full_payload_for_finance(self):
        # Operator cannot access payments at all, finance can see full payload.
        self.assertEqual(has_admin_permission(self.operator, "can_view_sensitive_payload"), False)
        self.assertEqual(has_admin_permission(self.finance, "can_view_sensitive_payload"), True)
        self.authenticate(self.finance)
        payment = PaymentTransaction.objects.get()

        response = self.client.get(f"/api/admin-console/payments/{payment.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["raw_payload"]["buyer_email"], "secret@example.com")

    def test_payment_serializer_masks_sensitive_payload_keys_case_insensitively(self):
        payment = PaymentTransaction.objects.get()
        payment.raw_payload = {
            "Buyer_Email": "secret@example.com",
            "Phone": "123456",
            "MOBILE": "987654",
            "trade_no": "ALI-1",
        }

        data = PaymentAdminSerializer(payment, context={"can_view_sensitive_payload": False}).data

        self.assertEqual(data["raw_payload"]["Buyer_Email"], "***")
        self.assertEqual(data["raw_payload"]["Phone"], "***")
        self.assertEqual(data["raw_payload"]["MOBILE"], "***")
        self.assertEqual(data["raw_payload"]["trade_no"], "ALI-1")
