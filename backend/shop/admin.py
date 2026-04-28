from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .codex_import import DEFAULT_CODEX_DESCRIPTION, import_codex_cards
from .models import AdminGuide, Announcement, CardSecret, Category, CodexImport, Product, SiteConfig


admin.site.site_header = "AI 发卡商城后台"
admin.site.site_title = "AI 发卡商城"
admin.site.index_title = "后台首页"
admin.site.empty_value_display = "-"


class CardImportForm(forms.Form):
    cards = forms.CharField(
        label="卡密内容",
        widget=forms.Textarea(
            attrs={
                "rows": 12,
                "placeholder": "每行一个卡密，例如：\nABC-123-001\nABC-123-002\nABC-123-003",
            }
        ),
        help_text="每行一个卡密，空行会被忽略；提交后系统会自动加密保存。",
    )


class CodexImportForm(forms.Form):
    price = forms.DecimalField(
        label="Codex 售价",
        min_value=0,
        decimal_places=2,
        max_digits=10,
        initial="99.00",
        help_text="前台展示和下单使用的价格。",
    )
    description = forms.CharField(
        label="商品说明",
        required=False,
        initial=DEFAULT_CODEX_DESCRIPTION,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    image_url = forms.URLField(label="商品图片地址", required=False)
    is_active = forms.BooleanField(label="前台上架", required=False, initial=True)
    cards = forms.CharField(
        label="粘贴卡密",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 12,
                "placeholder": "每行一个 Codex 卡密，例如：\nCODEX-AAAA-0001\nCODEX-BBBB-0002",
            }
        ),
        help_text="每行一个卡密。可以只粘贴，也可以和文件上传一起使用。",
    )
    upload = forms.FileField(
        label="上传 TXT/CSV",
        required=False,
        help_text="TXT 按行读取；CSV 读取每行第一个非空单元格。",
    )


@admin.register(AdminGuide)
class AdminGuideAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def changelist_view(self, request, extra_context=None):
        context = {
            **self.admin_site.each_context(request),
            "title": "后台使用指南",
            "category_add_url": reverse("admin:shop_category_add"),
            "product_add_url": reverse("admin:shop_product_add"),
            "product_list_url": reverse("admin:shop_product_changelist"),
            "announcement_add_url": reverse("admin:shop_announcement_add"),
            "site_config_url": reverse("admin:shop_siteconfig_changelist"),
            "order_list_url": reverse("admin:orders_order_changelist"),
            "codex_import_url": reverse("admin:shop_codeximport_changelist"),
        }
        return TemplateResponse(request, "admin/shop/guide.html", context)


@admin.register(CodexImport)
class CodexImportAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST":
            form = CodexImportForm(request.POST, request.FILES)
            if form.is_valid():
                result = import_codex_cards(
                    price=form.cleaned_data["price"],
                    description=form.cleaned_data["description"],
                    image_url=form.cleaned_data["image_url"],
                    is_active=form.cleaned_data["is_active"],
                    pasted_cards=form.cleaned_data["cards"],
                    uploaded_file=form.cleaned_data["upload"],
                )
                product = result["product"]
                messages.success(
                    request,
                    (
                        f"Codex 商品已更新；新增 {result['created_count']} 条卡密，"
                        f"跳过重复 {result['skipped_duplicate_count']} 条。"
                    ),
                )
                return redirect("admin:shop_product_change", product.id)
        else:
            form = CodexImportForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Codex 卡密一键导入",
            "form": form,
            "product_list_url": reverse("admin:shop_product_changelist"),
        }
        return TemplateResponse(request, "admin/shop/codex_import.html", context)


class CardSecretInline(admin.TabularInline):
    model = CardSecret
    fields = ("status", "reserved_order", "reserved_until", "sold_at")
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name = "卡密库存"
    verbose_name_plural = "该商品的卡密库存"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name", "slug")
    fieldsets = (
        ("分类信息", {"fields": ("name", "slug")}),
        ("展示设置", {"fields": ("sort_order", "is_active")}),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock_count", "is_active", "sort_order", "import_cards_link")
    list_filter = ("category", "is_active")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name", "description")
    inlines = [CardSecretInline]
    fieldsets = (
        ("商品基础信息", {"fields": ("category", "name", "description", "price")}),
        ("前台展示", {"fields": ("image_url", "is_active", "sort_order")}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:product_id>/import-cards/",
                self.admin_site.admin_view(self.import_cards),
                name="shop_product_import_cards",
            )
        ]
        return custom + urls

    @admin.display(description="可售库存")
    def stock_count(self, obj):
        return obj.available_stock

    @admin.display(description="补充库存")
    def import_cards_link(self, obj):
        url = reverse("admin:shop_product_import_cards", args=[obj.id])
        return format_html('<a class="button" href="{}">导入卡密</a>', url)

    def import_cards(self, request, product_id):
        product = Product.objects.get(pk=product_id)
        if request.method == "POST":
            form = CardImportForm(request.POST)
            if form.is_valid():
                rows = [row.strip() for row in form.cleaned_data["cards"].splitlines() if row.strip()]
                cards = []
                for row in rows:
                    card = CardSecret(product=product)
                    card.set_secret(row)
                    cards.append(card)
                CardSecret.objects.bulk_create(cards)
                messages.success(request, f"已为「{product.name}」导入 {len(cards)} 条卡密。")
                return redirect("admin:shop_product_changelist")
        else:
            form = CardImportForm()
        return render(request, "admin/shop/import_cards.html", {"form": form, "product": product})


@admin.register(CardSecret)
class CardSecretAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "status", "reserved_order", "reserved_until", "sold_at", "created_at")
    list_filter = ("status", "product")
    search_fields = ("product__name",)
    readonly_fields = ("product", "encrypted_secret", "status", "reserved_order", "reserved_until", "sold_at", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "sort_order", "created_at")
    list_editable = ("is_active", "sort_order")
    search_fields = ("title", "content")
    fieldsets = (
        ("公告内容", {"fields": ("title", "content")}),
        ("展示设置", {"fields": ("is_active", "sort_order")}),
    )


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "value")
    search_fields = ("key", "label", "value")
    fieldsets = (
        ("配置项", {"fields": ("key", "label", "value")}),
    )
