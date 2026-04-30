from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from admin_console.admin import AdminOperationLogAdmin
from admin_console.models import AdminOperationLog, AdminProfile
from admin_console.permissions import has_admin_permission


class AdminConsoleAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.factory = RequestFactory()
        self.User = get_user_model()

    def test_anonymous_user_cannot_access_me(self):
        response = self.client.get("/api/admin-console/me")

        self.assertEqual(response.status_code, 401)

    def test_non_staff_user_cannot_access_me(self):
        user = self.User.objects.create_user(
            username="buyer@example.com",
            email="buyer@example.com",
            password="Password123!",
        )
        self.client.force_authenticate(user)

        response = self.client.get("/api/admin-console/me")

        self.assertEqual(response.status_code, 403)

    def test_non_staff_user_with_admin_profile_cannot_access_me(self):
        user = self.User.objects.create_user(
            username="profiled-buyer@example.com",
            email="profiled-buyer@example.com",
            password="Password123!",
        )
        AdminProfile.objects.create(user=user)
        self.client.force_authenticate(user)

        response = self.client.get("/api/admin-console/me")

        self.assertEqual(response.status_code, 403)

    def test_inactive_staff_user_with_admin_profile_cannot_access_me(self):
        user = self.User.objects.create_user(
            username="inactive-operator@example.com",
            email="inactive-operator@example.com",
            password="Password123!",
            is_staff=True,
            is_active=False,
        )
        AdminProfile.objects.create(user=user)
        self.client.force_authenticate(user)

        response = self.client.get("/api/admin-console/me")

        self.assertEqual(response.status_code, 403)

    def test_staff_operator_can_access_me(self):
        user = self.User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=user, role=AdminProfile.Role.OPERATOR)
        self.client.force_authenticate(user)

        response = self.client.get("/api/admin-console/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "operator@example.com")
        self.assertEqual(response.data["role"], "operator")
        self.assertEqual(response.data["permissions"]["can_manage_inventory"], True)
        self.assertEqual(response.data["permissions"]["can_manage_staff"], False)

    def test_superuser_is_superadmin_without_profile(self):
        user = self.User.objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="Password123!",
        )
        self.client.force_authenticate(user)

        response = self.client.get("/api/admin-console/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "superadmin")
        self.assertEqual(response.data["permissions"]["can_manage_staff"], True)

    def test_admin_profile_defaults_to_operator_with_timestamps(self):
        user = self.User.objects.create_user(
            username="new-operator@example.com",
            email="new-operator@example.com",
            password="Password123!",
            is_staff=True,
        )

        profile = AdminProfile.objects.create(user=user)

        self.assertEqual(profile.role, AdminProfile.Role.OPERATOR)
        self.assertIsNotNone(profile.created_at)
        self.assertIsNotNone(profile.updated_at)

    def test_has_admin_permission_rejects_inactive_staff_user_with_profile(self):
        user = self.User.objects.create_user(
            username="inactive-permission@example.com",
            email="inactive-permission@example.com",
            password="Password123!",
            is_staff=True,
            is_active=False,
        )
        AdminProfile.objects.create(user=user)

        self.assertEqual(has_admin_permission(user, "can_manage_inventory"), False)

    def test_has_admin_permission_rejects_non_staff_superuser(self):
        user = self.User.objects.create_superuser(
            username="non-staff-root@example.com",
            email="non-staff-root@example.com",
            password="Password123!",
        )
        user.is_staff = False
        user.save(update_fields=["is_staff"])

        self.assertEqual(has_admin_permission(user, "can_manage_staff"), False)

    def test_admin_operation_log_admin_disables_delete(self):
        user = self.User.objects.create_superuser(
            username="admin-delete@example.com",
            email="admin-delete@example.com",
            password="Password123!",
        )
        request = self.factory.get("/admin/admin_console/adminoperationlog/")
        request.user = user
        model_admin = AdminOperationLogAdmin(AdminOperationLog, admin.site)

        self.assertEqual(model_admin.has_delete_permission(request), False)

    def test_audit_log_string_includes_action_and_actor(self):
        user = self.User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="Password123!",
            is_staff=True,
        )
        log = AdminOperationLog.objects.create(
            actor=user,
            actor_email=user.email,
            actor_role="operator",
            action="order.cancel",
            target_type="Order",
            target_id="1",
            reason="Customer requested cancellation",
        )

        self.assertIn("order.cancel", str(log))
        self.assertIn("operator@example.com", str(log))
