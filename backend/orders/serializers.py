from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers

from payments.gateway import build_payment_response
from .models import Order
from .services import DuplicatePendingOrder, create_order


class CreateOrderSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=20)
    contact = serializers.CharField(max_length=160)
    pay_type = serializers.ChoiceField(choices=["alipay", "wxpay", "qqpay"], default="alipay")

    def create(self, validated_data):
        try:
            return create_order(user=self.context["request"].user, **validated_data)
        except DuplicatePendingOrder as exc:
            raise serializers.ValidationError(
                {
                    "detail": str(exc),
                    "existing_order_no": exc.order.order_no,
                }
            ) from exc
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def to_representation(self, order):
        try:
            payment = build_payment_response(order, self.context["request"])
        except ImproperlyConfigured as exc:
            raise serializers.ValidationError({"payment": str(exc)}) from exc
        return {
            "order_no": order.order_no,
            "amount": str(order.amount),
            "expires_at": order.expires_at.isoformat(),
            "payment": payment,
        }


class OrderListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name")
    delivery_items = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "order_no",
            "product_name",
            "quantity",
            "contact",
            "amount",
            "status",
            "expires_at",
            "paid_at",
            "delivered_at",
            "delivery_items",
            "created_at",
        ]

    def get_delivery_items(self, obj):
        return obj.delivery_items if obj.status == Order.Status.PAID else []
