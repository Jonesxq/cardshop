from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework import serializers

from orders.models import Order, PaymentTransaction
from shop.models import Announcement, CardSecret, Category, Product, SiteConfig

from .models import AdminOperationLog, AdminProfile
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


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "sort_order", "is_active", "created_at"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "description",
            "price",
            "image_url",
            "is_active",
            "sort_order",
            "stock",
            "created_at",
            "updated_at",
        ]

    def get_stock(self, obj):
        stock_map = self.context.get("stock_counts_by_product", {})
        if obj.id in stock_map:
            return stock_map[obj.id]
        counts = {status: 0 for status, _label in CardSecret.Status.choices}
        for row in obj.cards.values("status").annotate(count=Count("id")):
            counts[row["status"]] = row["count"]
        return {
            "available": counts.get(CardSecret.Status.AVAILABLE, 0),
            "reserved": counts.get(CardSecret.Status.RESERVED, 0),
            "sold": counts.get(CardSecret.Status.SOLD, 0),
            "void": counts.get("void", 0),
        }

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value


class AnnouncementAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "title", "content", "is_active", "sort_order", "created_at"]


class SiteConfigAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfig
        fields = ["id", "key", "label", "value"]


class SiteConfigUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(required=False, allow_blank=True)
    value = serializers.CharField(required=False, allow_blank=True)


class UserAdminSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    order_count = serializers.IntegerField(read_only=True, default=0)
    total_paid_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=Decimal("0.00"))

    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "email",
            "username",
            "is_active",
            "is_staff",
            "is_superuser",
            "role",
            "order_count",
            "total_paid_amount",
        ]

    def get_role(self, obj):
        return get_admin_role(obj)


class UserAdminUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    role = serializers.ChoiceField(choices=AdminProfile.Role.choices, required=False)


class AdminOperationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminOperationLog
        fields = [
            "id",
            "actor_email",
            "actor_role",
            "action",
            "target_type",
            "target_id",
            "reason",
            "before",
            "after",
            "ip_address",
            "user_agent",
            "created_at",
        ]


class CardAdminSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    reserved_order_no = serializers.CharField(source="reserved_order.order_no", read_only=True)

    class Meta:
        model = CardSecret
        fields = [
            "id",
            "product",
            "product_name",
            "status",
            "reserved_order",
            "reserved_order_no",
            "reserved_until",
            "sold_at",
            "created_at",
        ]


class OrderAdminSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_no",
            "user",
            "user_email",
            "product",
            "product_name",
            "quantity",
            "contact",
            "amount",
            "pay_type",
            "status",
            "expires_at",
            "paid_at",
            "delivered_at",
            "delivery_items",
            "created_at",
            "updated_at",
        ]


class PaymentAdminSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source="order.order_no", read_only=True)
    raw_payload = serializers.SerializerMethodField()

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "order",
            "order_no",
            "provider",
            "trade_no",
            "out_trade_no",
            "amount",
            "status",
            "raw_payload",
            "note",
            "created_at",
        ]

    def get_raw_payload(self, obj):
        payload = dict(obj.raw_payload or {})
        if self.context.get("can_view_sensitive_payload"):
            return payload
        sensitive_keys = {"buyer_email", "email", "phone", "mobile"}
        for key in list(payload):
            if key.lower() in sensitive_keys:
                payload[key] = "***"
        return payload
