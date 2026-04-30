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

    def get_log(self, action):
        return AdminOperationLog.objects.get(action=action)

    def statuses_by_id(self, rows):
        return {row["id"]: row["status"] for row in rows}

    def test_mark_paid_delivers_order_and_writes_log(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        reserved_card = CardSecret.objects.get(reserved_order=order)

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/mark-paid",
            {"reason": "Confirmed bank transfer"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.delivery_items, ["CARD-001"])
        log = self.get_log("order.mark_paid")
        self.assertEqual(self.statuses_by_id(log.before["cards"])[reserved_card.id], CardSecret.Status.RESERVED)
        self.assertEqual(self.statuses_by_id(log.after["cards"])[reserved_card.id], CardSecret.Status.SOLD)
        self.assertEqual(log.after["payments"][0]["status"], PaymentTransaction.Status.SUCCESS)
        self.assertEqual(log.after["payments"][0]["provider"], "admin_console")

    def test_cancel_pending_order_releases_reserved_stock(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        reserved_card = CardSecret.objects.get(reserved_order=order)

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/cancel",
            {"reason": "Customer requested cancellation"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 3)
        log = self.get_log("order.cancel")
        self.assertEqual(log.after["status"], Order.Status.CANCELLED)
        self.assertEqual(self.statuses_by_id(log.after["cards"])[reserved_card.id], CardSecret.Status.AVAILABLE)

    def test_release_stock_expires_pending_order_and_releases_cards(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        reserved_card = CardSecret.objects.get(reserved_order=order)

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/release-stock",
            {"reason": "Manual stock release for abandoned payment"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 3)
        log = self.get_log("order.release_stock")
        self.assertEqual(log.after["status"], Order.Status.EXPIRED)
        self.assertEqual(self.statuses_by_id(log.after["cards"])[reserved_card.id], CardSecret.Status.AVAILABLE)

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
        log = self.get_log("order.redeliver")
        self.assertEqual(log.before["delivery_items"], ["CARD-001"])
        self.assertEqual(log.after["delivery_items"], ["CARD-001"])

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
        log = self.get_log("order.replace_card")
        before_cards = self.statuses_by_id(log.before["cards"])
        after_cards = self.statuses_by_id(log.after["cards"])
        old_card_id = CardSecret.objects.get(status=CardSecret.Status.VOID).id
        new_card_id = CardSecret.objects.get(status=CardSecret.Status.SOLD).id
        self.assertEqual(before_cards[old_card_id], CardSecret.Status.SOLD)
        self.assertEqual(after_cards[old_card_id], CardSecret.Status.VOID)
        self.assertEqual(after_cards[new_card_id], CardSecret.Status.SOLD)

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
        log = self.get_log("payment.resolve")
        self.assertEqual(log.before["status"], PaymentTransaction.Status.FAILED)
        self.assertEqual(log.after["status"], PaymentTransaction.Status.IGNORED)
        self.assertEqual(log.before["order"]["status"], Order.Status.PENDING)
        self.assertEqual(log.after["order"]["status"], Order.Status.PENDING)

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
