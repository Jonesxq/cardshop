from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from config import settings as project_settings
from shop.models import Announcement, Category, Product, SiteConfig


class DatabaseDefaultConfigTests(SimpleTestCase):
    def test_database_defaults_to_mysql_outside_tests(self):
        self.assertEqual(project_settings._default_db_engine(["manage.py", "migrate"]), "mysql")

    def test_database_defaults_to_sqlite_under_pytest(self):
        self.assertEqual(project_settings._default_db_engine(["pytest"]), "sqlite")

    def test_database_path_named_test_still_defaults_to_mysql_for_runtime_commands(self):
        self.assertEqual(project_settings._default_db_engine([r"D:\test\manage.py", "migrate"]), "mysql")


class SeedDemoEncodingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.User = get_user_model()

    def test_seed_demo_writes_readable_chinese_demo_data(self):
        call_command("seed_demo", verbosity=0)

        self.assertEqual(SiteConfig.objects.get(key="site_name").value, "AI 发卡商城")
        self.assertEqual(Category.objects.get(slug="ai-tools").name, "AI 工具")
        self.assertEqual(Category.objects.get(slug="digital").name, "数字权益")
        self.assertTrue(Announcement.objects.filter(title="购买须知").exists())

        product_names = set(Product.objects.values_list("name", flat=True))
        self.assertIn("AI 绘图点数包", product_names)
        self.assertIn("智能写作月卡", product_names)
        self.assertIn("云笔记高级兑换码", product_names)

        seeded_text = "\n".join(
            [
                *Category.objects.values_list("name", flat=True),
                *Product.objects.values_list("name", flat=True),
                *Product.objects.values_list("description", flat=True),
                *Announcement.objects.values_list("title", flat=True),
                *Announcement.objects.values_list("content", flat=True),
                *SiteConfig.objects.values_list("value", flat=True),
                *SiteConfig.objects.values_list("label", flat=True),
            ]
        )
        self.assertNotIn("鍙", seeded_text)
        self.assertNotIn("锛", seeded_text)
        self.assertNotIn("?", seeded_text)

    def test_seed_demo_creates_permanent_admin_login(self):
        call_command("seed_demo", verbosity=0)

        user = self.User.objects.get(username="xqwd528467")
        self.assertEqual(user.email, "xqwd528467@example.local")
        self.assertEqual(user.is_staff, True)
        self.assertEqual(user.is_superuser, True)
        self.assertTrue(user.check_password("528467"))

        response = self.client.post(
            "/api/auth/login",
            {"email": "xqwd528467", "password": "528467"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data["tokens"])

    def test_seed_demo_refreshes_existing_demo_admin_password(self):
        existing = self.User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="OldPassword123!",
            is_staff=False,
            is_superuser=False,
        )

        call_command("seed_demo", verbosity=0)

        existing.refresh_from_db()
        self.assertEqual(existing.is_staff, True)
        self.assertEqual(existing.is_superuser, True)
        self.assertTrue(existing.check_password("Admin12345!"))
