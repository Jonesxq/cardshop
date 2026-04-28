from django.contrib import admin, messages

from .models import Order, PaymentTransaction
from .services import complete_order_payment


@admin.action(description="确认已发货订单")
def resend_paid_orders(_modeladmin, request, queryset):
    count = 0
    for order in queryset.filter(status=Order.Status.PAID):
        if order.delivery_items:
            count += 1
    messages.success(request, f"已确认 {count} 个订单存在发货内容，可复制给用户。")


@admin.action(description="开发环境：标记支付成功并自动发货")
def mark_paid(_modeladmin, request, queryset):
    count = 0
    for order in queryset.filter(status=Order.Status.PENDING):
        complete_order_payment(order_no=order.order_no, amount=order.amount, provider="admin", raw_payload={})
        count += 1
    messages.success(request, f"已处理 {count} 个订单。")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "product", "quantity", "contact", "amount", "status", "created_at")
    list_filter = ("status", "product")
    search_fields = ("order_no", "contact", "product__name")
    readonly_fields = (
        "order_no",
        "user",
        "product",
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
    )
    fieldsets = (
        ("订单信息", {"fields": ("order_no", "user", "product", "quantity", "contact", "amount", "pay_type", "status")}),
        ("时间节点", {"fields": ("expires_at", "paid_at", "delivered_at", "created_at", "updated_at")}),
        ("发货内容", {"fields": ("delivery_items",)}),
    )
    actions = [resend_paid_orders, mark_paid]

    def has_add_permission(self, request):
        return False


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("provider", "out_trade_no", "trade_no", "amount", "status", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("out_trade_no", "trade_no")
    readonly_fields = ("order", "provider", "trade_no", "out_trade_no", "amount", "status", "raw_payload", "note", "created_at")

    def has_add_permission(self, request):
        return False
