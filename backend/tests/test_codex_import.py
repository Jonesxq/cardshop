from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from shop.codex_import import CODEX_CATEGORY_SLUG, CODEX_PRODUCT_NAME, import_codex_cards
from shop.models import CardSecret, Category, Product


class CodexImportServiceTests(TestCase):
    def test_first_import_creates_codex_category_product_and_cards(self):
        result = import_codex_cards(
            price="88.00",
            description="Codex 测试商品",
            pasted_cards="CODEX-001\n\nCODEX-002\n",
        )

        product = result["product"]
        self.assertEqual(product.name, CODEX_PRODUCT_NAME)
        self.assertEqual(product.category.slug, CODEX_CATEGORY_SLUG)
        self.assertEqual(product.price, Decimal("88.00"))
        self.assertEqual(result["created_count"], 2)
        self.assertEqual(CardSecret.objects.filter(product=product).count(), 2)
        self.assertEqual(
            {card.get_secret() for card in CardSecret.objects.filter(product=product)},
            {"CODEX-001", "CODEX-002"},
        )

    def test_next_import_updates_same_product(self):
        import_codex_cards(price="88.00", description="旧说明", pasted_cards="CODEX-001")

        result = import_codex_cards(price="128.00", description="新说明", image_url="", pasted_cards="CODEX-002")

        self.assertEqual(Product.objects.filter(name=CODEX_PRODUCT_NAME).count(), 1)
        product = result["product"]
        self.assertEqual(product.price, Decimal("128.00"))
        self.assertEqual(product.description, "新说明")
        self.assertEqual(CardSecret.objects.filter(product=product).count(), 2)

    def test_txt_upload_imports_lines(self):
        upload = SimpleUploadedFile("cards.txt", "TXT-001\n\nTXT-002\n".encode("utf-8"))

        result = import_codex_cards(price="99.00", description="", uploaded_file=upload)

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["uploaded_count"], 2)

    def test_csv_upload_imports_first_non_empty_cell(self):
        upload = SimpleUploadedFile(
            "cards.csv",
            "CSV-001,备注\n,CSV-002\n  CSV-003  ,其他\n".encode("utf-8-sig"),
            content_type="text/csv",
        )

        result = import_codex_cards(price="99.00", description="", uploaded_file=upload)

        product = result["product"]
        self.assertEqual(result["created_count"], 3)
        self.assertEqual(
            {card.get_secret() for card in CardSecret.objects.filter(product=product)},
            {"CSV-001", "CSV-002", "CSV-003"},
        )

    def test_duplicate_cards_are_skipped(self):
        import_codex_cards(price="99.00", description="", pasted_cards="DUP-001")

        result = import_codex_cards(
            price="99.00",
            description="",
            pasted_cards="DUP-001\nDUP-002\nDUP-002\n",
        )

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["skipped_duplicate_count"], 2)
        self.assertEqual(Category.objects.filter(slug=CODEX_CATEGORY_SLUG).count(), 1)


class CodexImportAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="Admin12345!",
        )
        self.client.force_login(self.admin_user)

    def test_admin_import_page_opens(self):
        response = self.client.get(reverse("admin:shop_codeximport_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Codex 卡密一键导入")

    def test_admin_post_imports_cards(self):
        response = self.client.post(
            reverse("admin:shop_codeximport_changelist"),
            {
                "price": "66.00",
                "description": "后台导入测试",
                "image_url": "",
                "is_active": "on",
                "cards": "ADMIN-001\nADMIN-002",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        product = Product.objects.get(name=CODEX_PRODUCT_NAME)
        self.assertEqual(product.price, Decimal("66.00"))
        self.assertEqual(CardSecret.objects.filter(product=product).count(), 2)

