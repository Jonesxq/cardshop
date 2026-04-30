from rest_framework.permissions import BasePermission

from .models import AdminProfile


ROLE_PERMISSIONS = {
    AdminProfile.Role.OPERATOR: {
        "can_manage_inventory": True,
        "can_manage_orders": True,
        "can_manage_payments": False,
        "can_manage_staff": False,
    },
    AdminProfile.Role.FINANCE: {
        "can_manage_inventory": False,
        "can_manage_orders": True,
        "can_manage_payments": True,
        "can_manage_staff": False,
    },
    AdminProfile.Role.SUPERADMIN: {
        "can_manage_inventory": True,
        "can_manage_orders": True,
        "can_manage_payments": True,
        "can_manage_staff": True,
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


def has_admin_permission(user, permission):
    role = get_admin_role(user)
    return bool(get_role_permissions(role).get(permission))


class IsAdminConsoleUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
            and get_admin_role(user)
        )
