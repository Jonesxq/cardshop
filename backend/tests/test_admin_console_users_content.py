from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from admin_console.models import AdminOperationLog, AdminProfile
from admin_console.permissions import ROLE_PERMISSIONS
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
            {"role": "finance", "is_staff": True, "is_active": True, "reason": "Promote for finance coverage"},
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
            {"role": "finance", "is_staff": False, "is_active": False, "reason": "Access review"},
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
        self.assertEqual(log.reason, "Access review")

    def test_staff_role_update_requires_reason(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.operator.id}",
            {"role": "finance", "is_staff": True, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.data)

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

    def test_superadmin_cannot_disable_self(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.superadmin.id}",
            {"is_active": False, "reason": "Disable myself"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.superadmin.refresh_from_db()
        self.assertEqual(self.superadmin.is_active, True)

    def test_superadmin_cannot_remove_own_staff_access(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.superadmin.id}",
            {"is_staff": False, "reason": "Remove myself"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.superadmin.refresh_from_db()
        self.assertEqual(self.superadmin.is_staff, True)

    def test_profile_superadmin_cannot_demote_self(self):
        User = get_user_model()
        profile_admin = User.objects.create_user(
            username="profile-admin@example.com",
            email="profile-admin@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=profile_admin, role=AdminProfile.Role.SUPERADMIN)
        self.authenticate(profile_admin)

        response = self.client.patch(
            f"/api/admin-console/users/{profile_admin.id}",
            {"role": "finance", "reason": "Demote myself"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        profile_admin.refresh_from_db()
        self.assertEqual(profile_admin.admin_profile.role, AdminProfile.Role.SUPERADMIN)

    def test_last_active_staff_superadmin_cannot_be_demoted(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.superadmin.id}",
            {"role": "finance", "reason": "Demote final admin"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_last_active_staff_superadmin_cannot_be_deactivated(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.superadmin.id}",
            {"is_active": False, "reason": "Deactivate final admin"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_last_superadmin_check_runs_inside_atomic_transaction(self):
        User = get_user_model()
        target_admin = User.objects.create_user(
            username="target-admin@example.com",
            email="target-admin@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=target_admin, role=AdminProfile.Role.SUPERADMIN)
        real_check = __import__(
            "admin_console.views",
            fromlist=["_has_active_staff_superadmin_excluding"],
        )._has_active_staff_superadmin_excluding
        atomic_states = []

        def asserting_check(*args, **kwargs):
            atomic_states.append(connection.in_atomic_block)
            return real_check(*args, **kwargs)

        self.authenticate(self.superadmin)
        with patch("admin_console.views._has_active_staff_superadmin_excluding", side_effect=asserting_check):
            response = self.client.patch(
                f"/api/admin-console/users/{target_admin.id}",
                {"role": "finance", "reason": "Demote secondary superadmin"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(atomic_states, [True])

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

    def test_site_config_update_rejects_invalid_key(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            "/api/admin-console/site-config/arbitrary_key",
            {"label": "Arbitrary", "value": "New"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SiteConfig.objects.filter(key="arbitrary_key").count(), 0)

    def test_site_config_update_requires_value(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            "/api/admin-console/site-config/site_name",
            {"label": "Site name"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("value", response.data)

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

    def test_operator_log_list_redacts_site_config_details(self):
        self.authenticate(self.operator)
        AdminOperationLog.objects.create(
            actor=self.superadmin,
            actor_email=self.superadmin.email,
            actor_role="superadmin",
            action="site_config.update",
            target_type="SiteConfig",
            target_id="site_name",
            before={"value": "Secret old"},
            after={"value": "Secret new"},
            ip_address="127.0.0.1",
            user_agent="Sensitive Browser",
        )

        response = self.client.get("/api/admin-console/logs")

        self.assertEqual(response.status_code, 200)
        log_data = response.data["results"][0]
        self.assertEqual(log_data["before"], {})
        self.assertEqual(log_data["after"], {})
        self.assertEqual(log_data["ip_address"], "")
        self.assertEqual(log_data["user_agent"], "")

    def test_operator_log_list_redacts_staff_update_details(self):
        self.authenticate(self.operator)
        AdminOperationLog.objects.create(
            actor=self.superadmin,
            actor_email=self.superadmin.email,
            actor_role="superadmin",
            action="user.update_staff",
            target_type="User",
            target_id=str(self.operator.id),
            before={"role": "operator", "is_staff": True},
            after={"role": "finance", "is_staff": True},
            ip_address="127.0.0.1",
            user_agent="Sensitive Browser",
        )

        response = self.client.get("/api/admin-console/logs")

        self.assertEqual(response.status_code, 200)
        log_data = response.data["results"][0]
        self.assertEqual(log_data["before"], {})
        self.assertEqual(log_data["after"], {})
        self.assertEqual(log_data["ip_address"], "")
        self.assertEqual(log_data["user_agent"], "")

    def test_superadmin_log_list_includes_site_config_details(self):
        self.authenticate(self.superadmin)
        AdminOperationLog.objects.create(
            actor=self.superadmin,
            actor_email=self.superadmin.email,
            actor_role="superadmin",
            action="site_config.update",
            target_type="SiteConfig",
            target_id="site_name",
            before={"value": "Secret old"},
            after={"value": "Secret new"},
            ip_address="127.0.0.1",
            user_agent="Sensitive Browser",
        )

        response = self.client.get("/api/admin-console/logs")

        self.assertEqual(response.status_code, 200)
        log_data = response.data["results"][0]
        self.assertEqual(log_data["before"], {"value": "Secret old"})
        self.assertEqual(log_data["after"], {"value": "Secret new"})
        self.assertEqual(log_data["ip_address"], "127.0.0.1")
        self.assertEqual(log_data["user_agent"], "Sensitive Browser")

    def test_staff_manager_log_list_includes_staff_update_details(self):
        User = get_user_model()
        staff_manager = User.objects.create_user(
            username="staff-manager@example.com",
            email="staff-manager@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=staff_manager, role=AdminProfile.Role.FINANCE)
        original_permission = ROLE_PERMISSIONS[AdminProfile.Role.FINANCE]["can_manage_staff"]
        ROLE_PERMISSIONS[AdminProfile.Role.FINANCE]["can_manage_staff"] = True
        self.addCleanup(
            lambda: ROLE_PERMISSIONS[AdminProfile.Role.FINANCE].__setitem__("can_manage_staff", original_permission)
        )
        self.authenticate(staff_manager)
        AdminOperationLog.objects.create(
            actor=self.superadmin,
            actor_email=self.superadmin.email,
            actor_role="superadmin",
            action="user.update_staff",
            target_type="User",
            target_id=str(self.operator.id),
            before={"role": "operator", "is_staff": True},
            after={"role": "finance", "is_staff": True},
            ip_address="127.0.0.1",
            user_agent="Sensitive Browser",
        )

        response = self.client.get("/api/admin-console/logs")

        self.assertEqual(response.status_code, 200)
        log_data = response.data["results"][0]
        self.assertEqual(log_data["before"], {"role": "operator", "is_staff": True})
        self.assertEqual(log_data["after"], {"role": "finance", "is_staff": True})
        self.assertEqual(log_data["ip_address"], "127.0.0.1")
        self.assertEqual(log_data["user_agent"], "Sensitive Browser")
