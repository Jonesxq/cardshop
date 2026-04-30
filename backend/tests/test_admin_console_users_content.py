from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from admin_console.models import AdminOperationLog, AdminProfile
from shop.models import Announcement, SiteConfig


class AdminConsoleUsersContentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="Password123!",
        )
        self.operator = User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.operator, role=AdminProfile.Role.OPERATOR)
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_superadmin_can_assign_staff_role(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.operator.id}",
            {"role": "finance", "is_staff": True, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.admin_profile.role, "finance")
        self.assertEqual(AdminOperationLog.objects.filter(action="user.update_staff").count(), 1)

    def test_staff_role_update_records_before_and_after(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.operator.id}",
            {"role": "finance", "is_staff": False, "is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        log = AdminOperationLog.objects.get(action="user.update_staff")
        self.assertEqual(log.before["role"], "operator")
        self.assertEqual(log.before["is_staff"], True)
        self.assertEqual(log.before["is_active"], True)
        self.assertEqual(log.after["role"], "finance")
        self.assertEqual(log.after["is_staff"], False)
        self.assertEqual(log.after["is_active"], False)

    def test_staff_role_update_rejects_invalid_role(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.operator.id}",
            {"role": "invalid", "is_staff": True, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_operator_cannot_assign_staff_role(self):
        self.authenticate(self.operator)

        response = self.client.patch(
            f"/api/admin-console/users/{self.operator.id}",
            {"role": "finance", "is_staff": True, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_superadmin_can_list_users_with_results(self):
        self.authenticate(self.superadmin)

        response = self.client.get("/api/admin-console/users", {"keyword": "operator"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["email"], "operator@example.com")
        self.assertIn("role", response.data["results"][0])
        self.assertIn("order_count", response.data["results"][0])
        self.assertIn("total_paid_amount", response.data["results"][0])

    def test_operator_can_create_announcement(self):
        self.authenticate(self.operator)

        response = self.client.post(
            "/api/admin-console/announcements",
            {"title": "Maintenance", "content": "Tonight", "is_active": True, "sort_order": 0},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Announcement.objects.get().title, "Maintenance")

    def test_superadmin_can_update_site_config(self):
        self.authenticate(self.superadmin)
        SiteConfig.objects.create(key="site_name", label="Site name", value="Old")

        response = self.client.patch(
            "/api/admin-console/site-config/site_name",
            {"label": "Site name", "value": "New"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SiteConfig.objects.get(key="site_name").value, "New")
        self.assertEqual(AdminOperationLog.objects.filter(action="site_config.update").count(), 1)

    def test_operator_cannot_view_site_config(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/site-config")

        self.assertEqual(response.status_code, 403)

    def test_logs_endpoint_returns_operation_logs(self):
        self.authenticate(self.superadmin)
        AdminOperationLog.objects.create(
            actor=self.operator,
            actor_email=self.operator.email,
            actor_role="operator",
            action="inventory.import",
            target_type="Product",
            target_id="1",
            reason="Restock",
        )

        response = self.client.get("/api/admin-console/logs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["action"], "inventory.import")
