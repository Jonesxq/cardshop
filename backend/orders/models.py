from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待支付"
        PAID = "paid", "已支付"
        EXPIRED = "expired", "已过期"
        CANCELLED = "cancelled", "已取消"

    order_no = models.CharField("订单号", max_length=32, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="下单用户",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    product = models.ForeignKey("shop.Product", verbose_name="商品", on_delete=models.PROTECT, related_name="orders")
    quantity = models.PositiveIntegerField("购买数量")
    contact = models.CharField("联系方式", max_length=160)
    amount = models.DecimalField("订单金额", max_digits=10, decimal_places=2)
    pay_type = models.CharField("支付方式", max_length=20, default="alipay")
    status = models.CharField("订单状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField("支付过期时间")
    paid_at = models.DateTimeField("支付时间", null=True, blank=True)
    delivered_at = models.DateTimeField("发货时间", null=True, blank=True)
    delivery_items = models.JSONField("发货内容", default=list, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["order_no"]),
            models.Index(fields=["contact"]),
            models.Index(fields=["status", "expires_at"]),
        ]
        ordering = ("-created_at",)
        verbose_name = "订单"
        verbose_name_plural = "订单"

    def __str__(self):
        return self.order_no


class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "成功"
        FAILED = "failed", "失败"
        IGNORED = "ignored", "已忽略"

    order = models.ForeignKey(Order, verbose_name="订单", on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField("支付渠道", max_length=40, default="easypay")
    trade_no = models.CharField("渠道流水号", max_length=80, blank=True)
    out_trade_no = models.CharField("商户订单号", max_length=80)
    amount = models.DecimalField("支付金额", max_digits=10, decimal_places=2)
    status = models.CharField("流水状态", max_length=16, choices=Status.choices)
    raw_payload = models.JSONField("原始回调", default=dict, blank=True)
    note = models.CharField("备注", max_length=255, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["out_trade_no"]),
            models.Index(fields=["trade_no"]),
        ]
        verbose_name = "支付流水"
        verbose_name_plural = "支付流水"

    def __str__(self):
        return f"{self.provider}:{self.out_trade_no}:{self.status}"
