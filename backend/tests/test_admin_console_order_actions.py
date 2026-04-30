from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from admin_console.models import AdminOperationLog, AdminProfile
from orders.models import Order, PaymentTransaction
from orders.services import create_order
from shop.models import CardSecret, Category, Product


class AdminConsoleOrderActionTests(TestCase):
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
        for value in ["CARD-001", "CARD-002", "CARD-003"]:
            card = CardSecret(product=self.product)
            card.set_secret(value)
            card.save()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_mark_paid_delivers_order_and_writes_log(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/mark-paid",
            {"reason": "Confirmed bank transfer"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.delivery_items, ["CARD-001"])
        self.assertEqual(AdminOperationLog.objects.filter(action="order.mark_paid").count(), 1)

    def test_cancel_pending_order_releases_reserved_stock(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/cancel",
            {"reason": "Customer requested cancellation"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 3)

    def test_release_stock_expires_pending_order_and_releases_cards(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/release-stock",
            {"reason": "Manual stock release for abandoned payment"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 3)

    def test_redeliver_paid_order_does_not_change_stock(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        self.client.post(
            f"/api/admin-console/orders/{order.id}/mark-paid",
            {"reason": "Confirmed bank transfer"},
            format="json",
        )

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/redeliver",
            {"reason": "Customer lost page"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["delivery_items"], ["CARD-001"])
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.SOLD).count(), 1)

    def test_replace_card_voids_old_card_and_delivers_new_card(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        self.client.post(
            f"/api/admin-console/orders/{order.id}/mark-paid",
            {"reason": "Confirmed bank transfer"},
            format="json",
        )

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/replace-card",
            {"reason": "Original card was invalid"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.delivery_items, ["CARD-002"])
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.VOID).count(), 1)
        self.assertEqual(AdminOperationLog.objects.filter(action="order.replace_card").count(), 1)

    def test_finance_cannot_replace_card(self):
        self.authenticate(self.finance)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/replace-card",
            {"reason": "Finance should not do this"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_finance_can_resolve_failed_payment(self):
        self.authenticate(self.finance)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        payment = PaymentTransaction.objects.create(
            order=order,
            provider="alipay",
            trade_no="ALI-FAILED",
            out_trade_no=order.order_no,
            amount=Decimal("1.00"),
            status=PaymentTransaction.Status.FAILED,
            raw_payload={"reason": "amount mismatch"},
        )

        response = self.client.post(
            f"/api/admin-console/payments/{payment.id}/resolve",
            {"reason": "Reviewed mismatch and marked as handled"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.IGNORED)
        self.assertIn("Reviewed mismatch", payment.note)
        self.assertEqual(AdminOperationLog.objects.filter(action="payment.resolve").count(), 1)

    def test_reason_is_required_for_order_actions(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/cancel",
            {"reason": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(AdminOperationLog.objects.count(), 0)

    def test_cancel_paid_order_is_denied(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        self.client.post(
            f"/api/admin-console/orders/{order.id}/mark-paid",
            {"reason": "Confirmed bank transfer"},
            format="json",
        )

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/cancel",
            {"reason": "Customer requested cancellation"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
