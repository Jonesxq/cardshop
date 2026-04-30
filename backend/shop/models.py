from django.db import models
from django.utils import timezone

from .crypto import decrypt_text, encrypt_text


class Category(models.Model):
    name = models.CharField("分类名称", max_length=80, unique=True, help_text="例如：AI 工具、数字权益。")
    slug = models.SlugField("分类标识", max_length=100, unique=True, help_text="英文或拼音，用在系统内部区分分类。")
    sort_order = models.PositiveIntegerField("排序", default=0, help_text="数字越小越靠前。")
    is_active = models.BooleanField("前台显示", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "商品分类"
        verbose_name_plural = "商品分类"

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        verbose_name="所属分类",
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField("商品名称", max_length=120)
    description = models.TextField("商品说明", blank=True, help_text="展示在前台商品卡片中，建议写清楚用途和交付内容。")
    price = models.DecimalField("售价", max_digits=10, decimal_places=2)
    image_url = models.URLField("商品图片地址", blank=True, help_text="可选；填写图片 URL 后前台会展示。")
    is_active = models.BooleanField("前台上架", default=True)
    sort_order = models.PositiveIntegerField("排序", default=0, help_text="数字越小越靠前。")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "商品"
        verbose_name_plural = "商品"

    def __str__(self):
        return self.name

    @property
    def available_stock(self):
        return self.cards.filter(status=CardSecret.Status.AVAILABLE).count()


class CardSecret(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "可售"
        RESERVED = "reserved", "已预留"
        SOLD = "sold", "已售出"
        VOID = "void", "Voided"

    product = models.ForeignKey(Product, verbose_name="所属商品", on_delete=models.CASCADE, related_name="cards")
    encrypted_secret = models.TextField("加密卡密")
    status = models.CharField("库存状态", max_length=16, choices=Status.choices, default=Status.AVAILABLE)
    reserved_order = models.ForeignKey(
        "orders.Order",
        verbose_name="预留订单",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reserved_cards",
    )
    reserved_until = models.DateTimeField("预留到期时间", null=True, blank=True)
    sold_at = models.DateTimeField("售出时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["product", "status"]),
            models.Index(fields=["reserved_until"]),
        ]
        verbose_name = "卡密库存"
        verbose_name_plural = "卡密库存"

    def __str__(self):
        return f"{self.product} #{self.id} {self.get_status_display()}"

    def set_secret(self, raw_secret):
        self.encrypted_secret = encrypt_text(raw_secret)

    def get_secret(self):
        return decrypt_text(self.encrypted_secret)

    def mark_sold(self):
        self.status = self.Status.SOLD
        self.sold_at = timezone.now()
        self.reserved_until = None


class Announcement(models.Model):
    title = models.CharField("公告标题", max_length=120)
    content = models.TextField("公告内容")
    is_active = models.BooleanField("前台显示", default=True)
    sort_order = models.PositiveIntegerField("排序", default=0, help_text="数字越小越靠前。")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "-created_at")
        verbose_name = "公告"
        verbose_name_plural = "公告"

    def __str__(self):
        return self.title


class SiteConfig(models.Model):
    key = models.CharField("配置键", max_length=80, unique=True, help_text="例如：site_name、support_contact。")
    value = models.TextField("配置值", blank=True)
    label = models.CharField("显示名称", max_length=120, blank=True)

    class Meta:
        verbose_name = "站点配置"
        verbose_name_plural = "站点配置"

    def __str__(self):
        return self.label or self.key


class AdminGuide(models.Model):
    class Meta:
        managed = False
        verbose_name = "后台使用指南"
        verbose_name_plural = "后台使用指南"


class CodexImport(models.Model):
    class Meta:
        managed = False
        verbose_name = "Codex 卡密一键导入"
        verbose_name_plural = "Codex 卡密一键导入"
