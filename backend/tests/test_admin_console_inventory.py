from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from admin_console.models import AdminOperationLog, AdminProfile
from shop.models import CardSecret, Category, Product


class AdminConsoleInventoryImportTests(TestCase):
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
        self.existing_card = CardSecret(product=self.product)
        self.existing_card.set_secret("EXISTING-001")
        self.existing_card.save()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def card_values(self):
        return {card.get_secret() for card in CardSecret.objects.filter(product=self.product)}

    def test_preview_reports_rejections_and_does_not_create_cards(self):
        self.authenticate(self.operator)

        response = self.client.post(
            "/api/admin-console/cards/import/preview",
            {
                "product_id": self.product.id,
                "cards": "NEW-001\n\nNEW-001\nEXISTING-001\nNEW-002\n   \nNEW-003",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product_id"], self.product.id)
        self.assertEqual(response.data["total_rows"], 7)
        self.assertEqual(response.data["valid_count"], 3)
        self.assertEqual(response.data["empty_count"], 2)
        self.assertEqual(response.data["same_batch_duplicate_count"], 1)
        self.assertEqual(response.data["existing_duplicate_count"], 1)
        self.assertNotIn("valid_values", response.data)
        self.assertEqual(CardSecret.objects.filter(product=self.product).count(), 1)
        rejected_statuses = {sample["status"] for sample in response.data["rejected_samples"]}
        self.assertIn("empty", rejected_statuses)
        self.assertIn("same_batch_duplicate", rejected_statuses)
        self.assertIn("existing_duplicate", rejected_statuses)

    def test_commit_creates_cards_skips_existing_duplicate_and_writes_audit_log(self):
        self.authenticate(self.operator)

        response = self.client.post(
            "/api/admin-console/cards/import/commit",
            {
                "product_id": self.product.id,
                "cards": "EXISTING-001\nNEW-010\nNEW-011\nNEW-010",
                "reason": "Restock Codex Card inventory",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product_id"], self.product.id)
        self.assertEqual(response.data["total_rows"], 4)
        self.assertEqual(response.data["valid_count"], 2)
        self.assertEqual(response.data["existing_duplicate_count"], 1)
        self.assertEqual(response.data["same_batch_duplicate_count"], 1)
        self.assertEqual(response.data["created_count"], 2)
        self.assertIsNotNone(response.data["log_id"])
        self.assertNotIn("valid_values", response.data)
        self.assertEqual(self.card_values(), {"EXISTING-001", "NEW-010", "NEW-011"})
        log = AdminOperationLog.objects.get(id=response.data["log_id"])
        self.assertEqual(log.action, "inventory.import")
        self.assertEqual(log.target_type, "Product")
        self.assertEqual(log.target_id, str(self.product.id))
        self.assertEqual(log.reason, "Restock Codex Card inventory")
        self.assertEqual(log.after["created_count"], 2)

    def test_commit_requires_non_empty_reason_and_creates_no_cards(self):
        self.authenticate(self.operator)

        response = self.client.post(
            "/api/admin-console/cards/import/commit",
            {
                "product_id": self.product.id,
                "cards": "NEW-020",
                "reason": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.data)
        self.assertEqual(self.card_values(), {"EXISTING-001"})
        self.assertEqual(AdminOperationLog.objects.count(), 0)

    def test_commit_rolls_back_card_creation_when_audit_log_fails(self):
        self.authenticate(self.operator)

        with patch.object(AdminOperationLog.objects, "create", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    "/api/admin-console/cards/import/commit",
                    {
                        "product_id": self.product.id,
                        "cards": "NEW-025",
                        "reason": "Restock with audit rollback",
                    },
                    format="json",
                )

        self.assertEqual(self.card_values(), {"EXISTING-001"})

    def test_finance_cannot_commit_cards(self):
        self.authenticate(self.finance)

        response = self.client.post(
            "/api/admin-console/cards/import/commit",
            {
                "product_id": self.product.id,
                "cards": "NEW-030",
                "reason": "Restock",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.card_values(), {"EXISTING-001"})

    def test_finance_cannot_preview_cards(self):
        self.authenticate(self.finance)

        response = self.client.post(
            "/api/admin-console/cards/import/preview",
            {"product_id": self.product.id, "cards": "NEW-040"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_card_secret_void_status_exists(self):
        self.assertEqual(CardSecret.Status.VOID, "void")
