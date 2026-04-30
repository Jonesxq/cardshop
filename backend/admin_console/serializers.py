from rest_framework import serializers

from .permissions import get_admin_role, get_role_permissions


class AdminMeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    role = serializers.CharField()
    permissions = serializers.DictField()


def serialize_admin_me(user):
    role = get_admin_role(user)
    data = {
        "id": user.id,
        "email": user.email,
        "role": role,
        "permissions": get_role_permissions(role),
    }
    return AdminMeSerializer(data).data
