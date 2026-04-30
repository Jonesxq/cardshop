from rest_framework.permissions import BasePermission

from .models import AdminProfile


ROLE_PERMISSIONS = {
    AdminProfile.Role.OPERATOR: {
        "can_view_dashboard": True,
        "can_manage_orders": True,
        "can_manage_products": True,
        "can_manage_inventory": True,
        "can_view_payments": False,
        "can_resolve_payments": False,
        "can_manage_users": False,
        "can_manage_staff": False,
        "can_view_sensitive_payload": False,
        "can_manage_settings": False,
        "can_view_logs": True,
        "can_manage_payments": False,
    },
    AdminProfile.Role.FINANCE: {
        "can_view_dashboard": True,
        "can_manage_orders": False,
        "can_manage_products": False,
        "can_manage_inventory": False,
        "can_view_payments": True,
        "can_resolve_payments": True,
        "can_manage_users": False,
        "can_manage_staff": False,
        "can_view_sensitive_payload": True,
        "can_manage_settings": False,
        "can_view_logs": True,
        "can_manage_payments": True,
    },
    AdminProfile.Role.SUPERADMIN: {
        "can_view_dashboard": True,
        "can_manage_orders": True,
        "can_manage_products": True,
        "can_manage_inventory": True,
        "can_view_payments": True,
        "can_resolve_payments": True,
        "can_manage_users": True,
        "can_manage_staff": True,
        "can_view_sensitive_payload": True,
        "can_manage_settings": True,
        "can_view_logs": True,
        "can_manage_payments": True,
    },
}


def get_admin_role(user):
    if not user or not user.is_authenticated:
        return ""
    if user.is_superuser:
        return AdminProfile.Role.SUPERADMIN
    try:
        return user.admin_profile.role
    except AdminProfile.DoesNotExist:
        return ""


def get_role_permissions(role):
    return ROLE_PERMISSIONS.get(role, {})


def is_admin_console_user(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.is_staff
        and get_admin_role(user)
    )


def has_admin_permission(user, permission):
    if not is_admin_console_user(user):
        return False
    role = get_admin_role(user)
    return bool(get_role_permissions(role).get(permission))


class IsAdminConsoleUser(BasePermission):
    def has_permission(self, request, view):
        return is_admin_console_user(request.user)
