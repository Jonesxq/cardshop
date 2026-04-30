# Admin Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete `/admin-console` operations backend for the card-delivery shop with role-based staff access, audit logs, dashboard metrics, management APIs, and Vue admin screens.

**Architecture:** Add a Django `admin_console` app for staff-only APIs, role profiles, audit logs, statistics, inventory import, and high-risk order/payment services. Add a Vue route group under `/admin-console` inside the existing frontend, reusing JWT authentication and Element Plus while keeping the storefront routes separate.

**Tech Stack:** Django 5.2, Django REST Framework, SimpleJWT, Vue 3, Vite, Pinia, Element Plus, Vitest for frontend helper tests.

---

## File Structure

Create backend files:

- `backend/admin_console/__init__.py`
- `backend/admin_console/apps.py`
- `backend/admin_console/admin.py`
- `backend/admin_console/audit.py`
- `backend/admin_console/dashboard.py`
- `backend/admin_console/inventory.py`
- `backend/admin_console/models.py`
- `backend/admin_console/order_actions.py`
- `backend/admin_console/permissions.py`
- `backend/admin_console/serializers.py`
- `backend/admin_console/urls.py`
- `backend/admin_console/views.py`
- `backend/admin_console/migrations/__init__.py`
- `backend/tests/test_admin_console_access.py`
- `backend/tests/test_admin_console_read_api.py`
- `backend/tests/test_admin_console_inventory.py`
- `backend/tests/test_admin_console_order_actions.py`
- `backend/tests/test_admin_console_users_content.py`

Modify backend files:

- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/shop/models.py`

Create frontend files:

- `frontend/src/api/adminConsole.js`
- `frontend/src/admin/permissions.js`
- `frontend/src/stores/adminSession.js`
- `frontend/src/views/admin/AdminConsoleLayout.vue`
- `frontend/src/views/admin/AdminForbiddenView.vue`
- `frontend/src/views/admin/DashboardView.vue`
- `frontend/src/views/admin/OrdersView.vue`
- `frontend/src/views/admin/ProductsView.vue`
- `frontend/src/views/admin/InventoryView.vue`
- `frontend/src/views/admin/PaymentsView.vue`
- `frontend/src/views/admin/UsersView.vue`
- `frontend/src/views/admin/ContentView.vue`
- `frontend/src/views/admin/LogsView.vue`
- `frontend/src/admin/permissions.spec.js`
- `frontend/src/stores/adminSession.spec.js`

Modify frontend files:

- `frontend/package.json`
- `frontend/src/router/index.js`
- `frontend/src/styles/main.css`

Do not stage the existing `docker-compose.yml` working-tree change unless the user explicitly asks for it.

## Task 1: Backend App, Roles, Audit Log, And `/me`

**Files:**

- Create: `backend/admin_console/__init__.py`
- Create: `backend/admin_console/apps.py`
- Create: `backend/admin_console/models.py`
- Create: `backend/admin_console/admin.py`
- Create: `backend/admin_console/audit.py`
- Create: `backend/admin_console/permissions.py`
- Create: `backend/admin_console/serializers.py`
- Create: `backend/admin_console/urls.py`
- Create: `backend/admin_console/views.py`
- Create: `backend/admin_console/migrations/__init__.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/config/urls.py`
- Test: `backend/tests/test_admin_console_access.py`

- [ ] **Step 1: Write the failing backend access tests**

Create `backend/tests/test_admin_console_access.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from admin_console.models import AdminOperationLog, AdminProfile


class AdminConsoleAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
cd backend
uv run pytest tests/test_admin_console_access.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'admin_console'`.

- [ ] **Step 3: Create the backend app files**

Create `backend/admin_console/apps.py`:

```python
from django.apps import AppConfig


class AdminConsoleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "admin_console"
    verbose_name = "Admin Console"
```

Create empty files:

```text
backend/admin_console/__init__.py
backend/admin_console/migrations/__init__.py
```

- [ ] **Step 4: Add models**

Create `backend/admin_console/models.py`:

```python
from django.conf import settings
from django.db import models


class AdminProfile(models.Model):
    class Role(models.TextChoices):
        OPERATOR = "operator", "Operator"
        FINANCE = "finance", "Finance"
        SUPERADMIN = "superadmin", "Super Admin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="User",
        on_delete=models.CASCADE,
        related_name="admin_profile",
    )
    role = models.CharField("Role", max_length=20, choices=Role.choices, default=Role.OPERATOR)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    class Meta:
        verbose_name = "Admin profile"
        verbose_name_plural = "Admin profiles"

    def __str__(self):
        return f"{self.user} ({self.role})"


class AdminOperationLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Actor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_operation_logs",
    )
    actor_email = models.EmailField("Actor email", blank=True)
    actor_role = models.CharField("Actor role", max_length=20, blank=True)
    action = models.CharField("Action", max_length=80)
    target_type = models.CharField("Target type", max_length=80)
    target_id = models.CharField("Target ID", max_length=80, blank=True)
    reason = models.TextField("Reason")
    before = models.JSONField("Before", default=dict, blank=True)
    after = models.JSONField("After", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("IP address", null=True, blank=True)
    user_agent = models.TextField("User agent", blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["actor_email"]),
        ]
        verbose_name = "Admin operation log"
        verbose_name_plural = "Admin operation logs"

    def __str__(self):
        return f"{self.action} by {self.actor_email or 'unknown'}"
```

- [ ] **Step 5: Add permissions and role helpers**

Create `backend/admin_console/permissions.py`:

```python
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
    },
}


def get_admin_role(user):
    if not getattr(user, "is_authenticated", False):
        return ""
    if user.is_superuser:
        return AdminProfile.Role.SUPERADMIN
    profile = getattr(user, "admin_profile", None)
    return profile.role if profile else ""


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
```

- [ ] **Step 6: Add audit helper**

Create `backend/admin_console/audit.py`:

```python
from .models import AdminOperationLog
from .permissions import get_admin_role


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_operation(*, request, action, target, reason, before=None, after=None):
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    log = AdminOperationLog.objects.create(
        actor=user,
        actor_email=getattr(user, "email", "") or "",
        actor_role=get_admin_role(user) or "",
        action=action,
        target_type=target.__class__.__name__ if target is not None else "",
        target_id=str(getattr(target, "pk", "")) if target is not None else "",
        reason=reason.strip(),
        before=before or {},
        after=after or {},
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return log
```

- [ ] **Step 7: Add serializers and `/me` view**

Create `backend/admin_console/serializers.py`:

```python
from rest_framework import serializers

from .permissions import get_admin_role, get_role_permissions


class AdminMeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField()
    role = serializers.CharField()
    permissions = serializers.DictField()


def serialize_admin_me(user):
    role = get_admin_role(user)
    return {
        "id": user.id,
        "email": user.email,
        "username": user.get_username(),
        "role": role,
        "permissions": get_role_permissions(role),
    }
```

Create `backend/admin_console/views.py`:

```python
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdminConsoleUser
from .serializers import serialize_admin_me


class AdminMeView(APIView):
    permission_classes = [IsAdminConsoleUser]

    def get(self, request):
        return Response(serialize_admin_me(request.user))
```

Create `backend/admin_console/urls.py`:

```python
from django.urls import path

from .views import AdminMeView

urlpatterns = [
    path("me", AdminMeView.as_view()),
]
```

- [ ] **Step 8: Register app, URLs, and Django Admin entries**

Modify `backend/config/settings.py` by adding `admin_console.apps.AdminConsoleConfig` after `payments.apps.PaymentsConfig`:

```python
    "payments.apps.PaymentsConfig",
    "admin_console.apps.AdminConsoleConfig",
]
```

Modify `backend/config/urls.py` by adding the route:

```python
    path("api/admin-console/", include("admin_console.urls")),
```

Create `backend/admin_console/admin.py`:

```python
from django.contrib import admin

from .models import AdminOperationLog, AdminProfile


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "created_at", "updated_at")
    list_filter = ("role",)
    search_fields = ("user__email", "user__username")


@admin.register(AdminOperationLog)
class AdminOperationLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor_email", "actor_role", "target_type", "target_id", "created_at")
    list_filter = ("action", "actor_role", "target_type")
    search_fields = ("actor_email", "target_id", "reason")
    readonly_fields = (
        "actor",
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
    )

    def has_add_permission(self, request):
        return False
```

- [ ] **Step 9: Create migrations and verify green**

Run:

```powershell
cd backend
uv run python manage.py makemigrations admin_console
uv run pytest tests/test_admin_console_access.py -q
uv run python manage.py check
```

Expected: tests PASS and `System check identified no issues`.

- [ ] **Step 10: Commit**

```powershell
git add backend/admin_console backend/config/settings.py backend/config/urls.py backend/tests/test_admin_console_access.py
git commit -m "feat: add admin console access control"
```

## Task 2: Backend Read And Update APIs Plus Dashboard

**Files:**

- Modify: `backend/admin_console/dashboard.py`
- Modify: `backend/admin_console/serializers.py`
- Modify: `backend/admin_console/urls.py`
- Modify: `backend/admin_console/views.py`
- Test: `backend/tests/test_admin_console_read_api.py`

- [ ] **Step 1: Write failing read API tests**

Create `backend/tests/test_admin_console_read_api.py`:

```python
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from admin_console.models import AdminProfile
from orders.models import Order, PaymentTransaction
from shop.models import Announcement, CardSecret, Category, Product, SiteConfig


class AdminConsoleReadApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.operator = User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.operator, role=AdminProfile.Role.OPERATOR)
        self.finance = User.objects.create_user(
            username="finance@example.com",
            email="finance@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.finance, role=AdminProfile.Role.FINANCE)
        self.client = APIClient()
        self.category = Category.objects.create(name="AI Tools", slug="ai-tools")
        self.product = Product.objects.create(
            category=self.category,
            name="Codex Card",
            price=Decimal("99.00"),
            is_active=True,
        )
        card = CardSecret(product=self.product)
        card.set_secret("CARD-001")
        card.save()
        self.order = Order.objects.create(
            order_no="O202604300001",
            product=self.product,
            quantity=1,
            contact="buyer@example.com",
            amount=Decimal("99.00"),
            status=Order.Status.PAID,
            expires_at=timezone.now() + timezone.timedelta(minutes=15),
            paid_at=timezone.now(),
            delivered_at=timezone.now(),
            delivery_items=["CARD-001"],
        )
        PaymentTransaction.objects.create(
            order=self.order,
            provider="alipay",
            trade_no="ALI-1",
            out_trade_no=self.order.order_no,
            amount=Decimal("99.00"),
            status=PaymentTransaction.Status.SUCCESS,
            raw_payload={"buyer_email": "secret@example.com", "trade_no": "ALI-1"},
        )
        Announcement.objects.create(title="Notice", content="Content", is_active=True)
        SiteConfig.objects.create(key="site_name", label="Site name", value="AI Shop")

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_dashboard_returns_metrics_and_task_lists(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["today_order_count"], 1)
        self.assertEqual(response.data["summary"]["today_paid_amount"], "99.00")
        self.assertEqual(response.data["top_products"][0]["name"], "Codex Card")

    def test_products_list_includes_stock_count(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["name"], "Codex Card")
        self.assertEqual(response.data["results"][0]["stock"]["available"], 1)

    def test_operator_can_patch_product_status(self):
        self.authenticate(self.operator)

        response = self.client.patch(
            f"/api/admin-console/products/{self.product.id}",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.is_active, False)

    def test_cards_list_does_not_expose_plain_secret(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/cards")

        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.data["results"][0])
        self.assertNotIn("encrypted_secret", response.data["results"][0])
        self.assertNotIn("CARD-001", str(response.data))

    def test_operator_cannot_list_payment_transactions(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/payments")

        self.assertEqual(response.status_code, 403)

    def test_finance_can_list_payment_transactions_with_raw_payload(self):
        self.authenticate(self.finance)

        response = self.client.get("/api/admin-console/payments")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["raw_payload"]["buyer_email"], "secret@example.com")

    def test_orders_filter_by_status(self):
        self.authenticate(self.operator)

        response = self.client.get("/api/admin-console/orders", {"status": "paid"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["order_no"], "O202604300001")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
cd backend
uv run pytest tests/test_admin_console_read_api.py -q
```

Expected: FAIL with `404` for `/api/admin-console/dashboard` or missing view imports.

- [ ] **Step 3: Implement dashboard data builder**

Create `backend/admin_console/dashboard.py`:

```python
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from orders.models import Order, PaymentTransaction
from shop.models import CardSecret, Product


def decimal_string(value):
    return str((value or Decimal("0.00")).quantize(Decimal("0.01")))


def get_dashboard_payload():
    now = timezone.now()
    today = timezone.localdate(now)
    today_orders = Order.objects.filter(created_at__date=today)
    paid_orders = Order.objects.filter(status=Order.Status.PAID)
    low_stock_queryset = (
        Product.objects.select_related("category")
        .annotate(available_stock=Count("cards", filter=Q(cards__status=CardSecret.Status.AVAILABLE)))
        .filter(is_active=True, available_stock__lte=5)
        .order_by("available_stock", "sort_order", "id")
    )
    low_stock_products = low_stock_queryset[:8]
    abnormal_payments = PaymentTransaction.objects.exclude(status=PaymentTransaction.Status.SUCCESS).order_by("-created_at")[:8]
    trend_start = today - timezone.timedelta(days=6)
    trend_rows = (
        paid_orders.filter(paid_at__date__gte=trend_start)
        .annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(order_count=Count("id"), paid_amount=Sum("amount"))
        .order_by("day")
    )
    top_products = (
        paid_orders.values("product_id", "product__name")
        .annotate(order_count=Count("id"), paid_amount=Sum("amount"))
        .order_by("-paid_amount", "-order_count")[:8]
    )
    return {
        "summary": {
            "today_order_count": today_orders.count(),
            "today_paid_amount": decimal_string(today_orders.filter(status=Order.Status.PAID).aggregate(total=Sum("amount"))["total"]),
            "pending_order_count": Order.objects.filter(status=Order.Status.PENDING).count(),
            "low_stock_product_count": low_stock_queryset.count(),
            "abnormal_payment_count": PaymentTransaction.objects.exclude(status=PaymentTransaction.Status.SUCCESS).count(),
        },
        "low_stock_products": [
            {
                "id": product.id,
                "name": product.name,
                "category_name": product.category.name,
                "available_stock": product.available_stock,
            }
            for product in low_stock_products
        ],
        "abnormal_payments": [
            {
                "id": payment.id,
                "provider": payment.provider,
                "out_trade_no": payment.out_trade_no,
                "status": payment.status,
                "amount": str(payment.amount),
                "created_at": payment.created_at.isoformat(),
            }
            for payment in abnormal_payments
        ],
        "trend": [
            {
                "day": row["day"].isoformat(),
                "order_count": row["order_count"],
                "paid_amount": decimal_string(row["paid_amount"]),
            }
            for row in trend_rows
        ],
        "top_products": [
            {
                "id": row["product_id"],
                "name": row["product__name"],
                "order_count": row["order_count"],
                "paid_amount": decimal_string(row["paid_amount"]),
            }
            for row in top_products
        ],
    }
```

- [ ] **Step 4: Add read serializers**

Append to `backend/admin_console/serializers.py`:

```python
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import serializers

from orders.models import Order, PaymentTransaction
from shop.models import Announcement, CardSecret, Category, Product, SiteConfig


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
        counts = obj.cards.values("status").annotate(count=Count("id"))
        by_status = {item["status"]: item["count"] for item in counts}
        return {
            "available": by_status.get(CardSecret.Status.AVAILABLE, 0),
            "reserved": by_status.get(CardSecret.Status.RESERVED, 0),
            "sold": by_status.get(CardSecret.Status.SOLD, 0),
            "void": by_status.get(getattr(CardSecret.Status, "VOID", "void"), 0),
        }


class OrderAdminSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True, allow_null=True)

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
        payload = obj.raw_payload or {}
        can_view = bool(self.context.get("can_view_sensitive_payload"))
        if can_view:
            return payload
        return {key: "***" if key.lower() in {"buyer_email", "email", "phone", "mobile"} else value for key, value in payload.items()}


class CardAdminSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    reserved_order_no = serializers.CharField(source="reserved_order.order_no", read_only=True, allow_null=True)

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


class AnnouncementAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "title", "content", "is_active", "sort_order", "created_at"]


class SiteConfigAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfig
        fields = ["id", "key", "label", "value"]
```

- [ ] **Step 5: Add list views**

Append to `backend/admin_console/views.py`:

```python
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied

from orders.models import Order, PaymentTransaction
from shop.models import CardSecret, Category, Product
from .dashboard import get_dashboard_payload
from .permissions import has_admin_permission
from .serializers import CardAdminSerializer, CategorySerializer, OrderAdminSerializer, PaymentAdminSerializer, ProductSerializer


class AdminPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class RequirePermissionMixin:
    required_permission = ""
    pagination_class = AdminPagination

    def check_permissions(self, request):
        super().check_permissions(request)
        if self.required_permission and not has_admin_permission(request.user, self.required_permission):
            raise PermissionDenied("Permission denied")


class AdminDashboardView(APIView):
    permission_classes = [IsAdminConsoleUser]

    def get(self, request):
        if not has_admin_permission(request.user, "can_view_dashboard"):
            raise PermissionDenied("Permission denied")
        return Response(get_dashboard_payload())


class ProductListCreateView(RequirePermissionMixin, generics.ListCreateAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_products"
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.select_related("category").prefetch_related("cards").order_by("sort_order", "id")
        keyword = self.request.query_params.get("keyword", "").strip()
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        return queryset


class CategoryListCreateView(RequirePermissionMixin, generics.ListCreateAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_products"
    serializer_class = CategorySerializer
    queryset = Category.objects.order_by("sort_order", "id")


class OrderListView(RequirePermissionMixin, generics.ListAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_orders"
    serializer_class = OrderAdminSerializer

    def get_queryset(self):
        queryset = Order.objects.select_related("product", "user").order_by("-created_at")
        status_value = self.request.query_params.get("status", "").strip()
        keyword = self.request.query_params.get("keyword", "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)
        if keyword:
            queryset = queryset.filter(Q(order_no__icontains=keyword) | Q(contact__icontains=keyword))
        return queryset


class PaymentListView(RequirePermissionMixin, generics.ListAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_view_payments"
    serializer_class = PaymentAdminSerializer

    def get_queryset(self):
        queryset = PaymentTransaction.objects.select_related("order").order_by("-created_at")
        status_value = self.request.query_params.get("status", "").strip()
        provider = self.request.query_params.get("provider", "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)
        if provider:
            queryset = queryset.filter(provider=provider)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["can_view_sensitive_payload"] = has_admin_permission(self.request.user, "can_view_sensitive_payload")
        return context


class ProductDetailView(RequirePermissionMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_products"
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("category").prefetch_related("cards")


class CategoryDetailView(RequirePermissionMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_products"
    serializer_class = CategorySerializer
    queryset = Category.objects.all()


class CardListView(RequirePermissionMixin, generics.ListAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_inventory"
    serializer_class = CardAdminSerializer

    def get_queryset(self):
        queryset = CardSecret.objects.select_related("product", "reserved_order").order_by("-created_at", "-id")
        product_id = self.request.query_params.get("product_id", "").strip()
        status_value = self.request.query_params.get("status", "").strip()
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset


class OrderDetailView(RequirePermissionMixin, generics.RetrieveAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_orders"
    serializer_class = OrderAdminSerializer
    queryset = Order.objects.select_related("product", "user")


class PaymentDetailView(RequirePermissionMixin, generics.RetrieveAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_view_payments"
    serializer_class = PaymentAdminSerializer
    queryset = PaymentTransaction.objects.select_related("order")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["can_view_sensitive_payload"] = has_admin_permission(self.request.user, "can_view_sensitive_payload")
        return context
```

- [ ] **Step 6: Wire URLs**

Modify `backend/admin_console/urls.py`:

```python
from django.urls import path

from .views import (
    AdminDashboardView,
    AdminMeView,
    CardListView,
    CategoryListCreateView,
    CategoryDetailView,
    OrderDetailView,
    OrderListView,
    PaymentDetailView,
    PaymentListView,
    ProductDetailView,
    ProductListCreateView,
)

urlpatterns = [
    path("me", AdminMeView.as_view()),
    path("dashboard", AdminDashboardView.as_view()),
    path("products", ProductListCreateView.as_view()),
    path("products/<int:pk>", ProductDetailView.as_view()),
    path("categories", CategoryListCreateView.as_view()),
    path("categories/<int:pk>", CategoryDetailView.as_view()),
    path("cards", CardListView.as_view()),
    path("orders", OrderListView.as_view()),
    path("orders/<int:pk>", OrderDetailView.as_view()),
    path("payments", PaymentListView.as_view()),
    path("payments/<int:pk>", PaymentDetailView.as_view()),
]
```

- [ ] **Step 7: Run tests**

Run:

```powershell
cd backend
uv run pytest tests/test_admin_console_read_api.py tests/test_admin_console_access.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add backend/admin_console backend/tests/test_admin_console_read_api.py
git commit -m "feat: add admin console read APIs"
```

## Task 3: Inventory Status, Preview, Commit, And Audit

**Files:**

- Modify: `backend/shop/models.py`
- Create/modify: `backend/admin_console/inventory.py`
- Modify: `backend/admin_console/serializers.py`
- Modify: `backend/admin_console/views.py`
- Modify: `backend/admin_console/urls.py`
- Test: `backend/tests/test_admin_console_inventory.py`

- [ ] **Step 1: Write failing inventory tests**

Create `backend/tests/test_admin_console_inventory.py`:

```python
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from admin_console.models import AdminOperationLog, AdminProfile
from shop.models import CardSecret, Category, Product


class AdminConsoleInventoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.operator = User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.operator, role=AdminProfile.Role.OPERATOR)
        self.finance = User.objects.create_user(
            username="finance@example.com",
            email="finance@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.finance, role=AdminProfile.Role.FINANCE)
        self.client = APIClient()
        self.category = Category.objects.create(name="AI Tools", slug="ai-tools")
        self.product = Product.objects.create(
            category=self.category,
            name="Codex Card",
            price=Decimal("99.00"),
            is_active=True,
        )
        card = CardSecret(product=self.product)
        card.set_secret("EXISTING-001")
        card.save()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_preview_reports_empty_same_batch_and_existing_duplicates(self):
        self.authenticate(self.operator)

        response = self.client.post(
            "/api/admin-console/cards/import/preview",
            {
                "product_id": self.product.id,
                "cards": "NEW-001\n\nNEW-001\nEXISTING-001\nNEW-002",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_rows"], 5)
        self.assertEqual(response.data["valid_count"], 2)
        self.assertEqual(response.data["empty_count"], 1)
        self.assertEqual(response.data["same_batch_duplicate_count"], 1)
        self.assertEqual(response.data["existing_duplicate_count"], 1)

    def test_commit_creates_cards_and_audit_log(self):
        self.authenticate(self.operator)

        response = self.client.post(
            "/api/admin-console/cards/import/commit",
            {
                "product_id": self.product.id,
                "cards": "NEW-001\nEXISTING-001\nNEW-002",
                "reason": "Weekly restock",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created_count"], 2)
        self.assertEqual(response.data["existing_duplicate_count"], 1)
        self.assertEqual(CardSecret.objects.filter(product=self.product).count(), 3)
        self.assertEqual(AdminOperationLog.objects.filter(action="inventory.import").count(), 1)

    def test_finance_cannot_import_cards(self):
        self.authenticate(self.finance)

        response = self.client.post(
            "/api/admin-console/cards/import/commit",
            {"product_id": self.product.id, "cards": "NEW-001", "reason": "Restock"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
cd backend
uv run pytest tests/test_admin_console_inventory.py -q
```

Expected: FAIL with `404` for the import endpoints.

- [ ] **Step 3: Extend card status with voided state**

Modify `backend/shop/models.py` inside `CardSecret.Status`:

```python
        VOID = "void", "Voided"
```

Leave `backend/shop/admin.py` unchanged. Its existing `CardSecretAdmin.list_filter = ("status", "product")` will show the new status choice.

Run:

```powershell
cd backend
uv run python manage.py makemigrations shop
```

Expected: one migration altering `CardSecret.status` choices.

- [ ] **Step 4: Add inventory service**

Create `backend/admin_console/inventory.py`:

```python
from dataclasses import dataclass

from django.db import transaction

from shop.models import CardSecret, Product


@dataclass
class ImportRow:
    row_number: int
    value: str
    status: str


def parse_card_text(text):
    rows = []
    seen = set()
    empty_count = 0
    same_batch_duplicate_count = 0
    for index, raw in enumerate((text or "").splitlines(), start=1):
        value = raw.strip()
        if not value:
            empty_count += 1
            rows.append(ImportRow(index, "", "empty"))
            continue
        if value in seen:
            same_batch_duplicate_count += 1
            rows.append(ImportRow(index, value, "same_batch_duplicate"))
            continue
        seen.add(value)
        rows.append(ImportRow(index, value, "candidate"))
    return rows, empty_count, same_batch_duplicate_count


def build_import_preview(*, product, cards):
    rows, empty_count, same_batch_duplicate_count = parse_card_text(cards)
    candidates = [row.value for row in rows if row.status == "candidate"]
    existing_values = set()
    for card in CardSecret.objects.filter(product=product):
        try:
            existing_values.add(card.get_secret())
        except Exception:
            continue
    valid_values = []
    existing_duplicate_count = 0
    rejected_samples = []
    for row in rows:
        if row.status == "empty":
            if len(rejected_samples) < 10:
                rejected_samples.append({"row": row.row_number, "value": "", "reason": "empty"})
            continue
        if row.status == "same_batch_duplicate":
            if len(rejected_samples) < 10:
                rejected_samples.append({"row": row.row_number, "value": row.value, "reason": "same_batch_duplicate"})
            continue
        if row.value in existing_values:
            existing_duplicate_count += 1
            if len(rejected_samples) < 10:
                rejected_samples.append({"row": row.row_number, "value": row.value, "reason": "existing_duplicate"})
            continue
        valid_values.append(row.value)
    return {
        "product_id": product.id,
        "total_rows": len(rows),
        "valid_count": len(valid_values),
        "empty_count": empty_count,
        "same_batch_duplicate_count": same_batch_duplicate_count,
        "existing_duplicate_count": existing_duplicate_count,
        "valid_values": valid_values,
        "rejected_samples": rejected_samples,
    }


@transaction.atomic
def commit_card_import(*, product_id, cards):
    product = Product.objects.select_for_update().get(id=product_id)
    preview = build_import_preview(product=product, cards=cards)
    created = []
    for value in preview["valid_values"]:
        card = CardSecret(product=product)
        card.set_secret(value)
        created.append(card)
    CardSecret.objects.bulk_create(created)
    return product, {
        key: value
        for key, value in preview.items()
        if key != "valid_values"
    } | {"created_count": len(created)}
```

- [ ] **Step 5: Add views and URLs**

Append to `backend/admin_console/views.py`:

```python
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import ValidationError

from .audit import record_operation
from .inventory import build_import_preview, commit_card_import


class CardImportRequestSerializer(drf_serializers.Serializer):
    product_id = drf_serializers.IntegerField()
    cards = drf_serializers.CharField(allow_blank=True)
    reason = drf_serializers.CharField(required=False, allow_blank=True)


class CardImportPreviewView(RequirePermissionMixin, APIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_inventory"

    def post(self, request):
        self.check_permissions(request)
        serializer = CardImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = Product.objects.get(id=serializer.validated_data["product_id"])
        preview = build_import_preview(product=product, cards=serializer.validated_data["cards"])
        preview.pop("valid_values", None)
        return Response(preview)


class CardImportCommitView(RequirePermissionMixin, APIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_inventory"

    def post(self, request):
        self.check_permissions(request)
        serializer = CardImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "").strip()
        if not reason:
            raise ValidationError({"detail": "Reason is required"})
        product, result = commit_card_import(
            product_id=serializer.validated_data["product_id"],
            cards=serializer.validated_data["cards"],
        )
        log = record_operation(
            request=request,
            action="inventory.import",
            target=product,
            reason=reason,
            before={},
            after=result,
        )
        result["log_id"] = log.id
        return Response(result)
```

Add URL paths:

```python
    path("cards/import/preview", CardImportPreviewView.as_view()),
    path("cards/import/commit", CardImportCommitView.as_view()),
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd backend
uv run pytest tests/test_admin_console_inventory.py tests/test_admin_console_read_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/admin_console backend/shop/models.py backend/shop/migrations backend/tests/test_admin_console_inventory.py
git commit -m "feat: add admin console inventory import"
```

## Task 4: Order Actions And Payment Resolution

**Files:**

- Create/modify: `backend/admin_console/order_actions.py`
- Modify: `backend/admin_console/views.py`
- Modify: `backend/admin_console/urls.py`
- Test: `backend/tests/test_admin_console_order_actions.py`

- [ ] **Step 1: Write failing order action tests**

Create `backend/tests/test_admin_console_order_actions.py`:

```python
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from admin_console.models import AdminOperationLog, AdminProfile
from orders.models import Order, PaymentTransaction
from orders.services import create_order
from shop.models import CardSecret, Category, Product


class AdminConsoleOrderActionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.operator = User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.operator, role=AdminProfile.Role.OPERATOR)
        self.finance = User.objects.create_user(
            username="finance@example.com",
            email="finance@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.finance, role=AdminProfile.Role.FINANCE)
        self.client = APIClient()
        self.category = Category.objects.create(name="AI Tools", slug="ai-tools")
        self.product = Product.objects.create(
            category=self.category,
            name="Codex Card",
            price=Decimal("99.00"),
            is_active=True,
        )
        for value in ["CARD-001", "CARD-002", "CARD-003"]:
            card = CardSecret(product=self.product)
            card.set_secret(value)
            card.save()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_mark_paid_delivers_order_and_writes_log(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/mark-paid",
            {"reason": "Confirmed bank transfer"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.delivery_items, ["CARD-001"])
        self.assertEqual(AdminOperationLog.objects.filter(action="order.mark_paid").count(), 1)

    def test_cancel_pending_order_releases_reserved_stock(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/cancel",
            {"reason": "Customer requested cancellation"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 3)

    def test_release_stock_expires_pending_order_and_releases_cards(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/release-stock",
            {"reason": "Manual stock release for abandoned payment"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.AVAILABLE).count(), 3)

    def test_redeliver_paid_order_does_not_change_stock(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        self.client.post(
            f"/api/admin-console/orders/{order.id}/mark-paid",
            {"reason": "Confirmed bank transfer"},
            format="json",
        )

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/redeliver",
            {"reason": "Customer lost page"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["delivery_items"], ["CARD-001"])
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.SOLD).count(), 1)

    def test_replace_card_voids_old_card_and_delivers_new_card(self):
        self.authenticate(self.operator)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        self.client.post(
            f"/api/admin-console/orders/{order.id}/mark-paid",
            {"reason": "Confirmed bank transfer"},
            format="json",
        )

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/replace-card",
            {"reason": "Original card was invalid"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.delivery_items, ["CARD-002"])
        self.assertEqual(CardSecret.objects.filter(status=CardSecret.Status.VOID).count(), 1)
        self.assertEqual(AdminOperationLog.objects.filter(action="order.replace_card").count(), 1)

    def test_finance_cannot_replace_card(self):
        self.authenticate(self.finance)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")

        response = self.client.post(
            f"/api/admin-console/orders/{order.id}/replace-card",
            {"reason": "Finance should not do this"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_finance_can_resolve_failed_payment(self):
        self.authenticate(self.finance)
        order = create_order(product_id=self.product.id, quantity=1, contact="buyer@example.com")
        payment = PaymentTransaction.objects.create(
            order=order,
            provider="alipay",
            trade_no="ALI-FAILED",
            out_trade_no=order.order_no,
            amount=Decimal("1.00"),
            status=PaymentTransaction.Status.FAILED,
            raw_payload={"reason": "amount mismatch"},
        )

        response = self.client.post(
            f"/api/admin-console/payments/{payment.id}/resolve",
            {"reason": "Reviewed mismatch and marked as handled"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.IGNORED)
        self.assertIn("Reviewed mismatch", payment.note)
        self.assertEqual(AdminOperationLog.objects.filter(action="payment.resolve").count(), 1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
cd backend
uv run pytest tests/test_admin_console_order_actions.py -q
```

Expected: FAIL with `404` for action endpoints.

- [ ] **Step 3: Implement order action services**

Create `backend/admin_console/order_actions.py`:

```python
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from orders.services import complete_order_payment
from shop.models import CardSecret


def order_snapshot(order):
    return {
        "id": order.id,
        "order_no": order.order_no,
        "status": order.status,
        "delivery_items": list(order.delivery_items or []),
    }


@transaction.atomic
def admin_mark_paid(order_id):
    order = Order.objects.select_for_update().get(id=order_id)
    before = order_snapshot(order)
    complete_order_payment(order_no=order.order_no, amount=order.amount, provider="admin_console", raw_payload={})
    order.refresh_from_db()
    return order, before, order_snapshot(order)


@transaction.atomic
def admin_cancel_order(order_id):
    order = Order.objects.select_for_update().get(id=order_id)
    before = order_snapshot(order)
    if order.status == Order.Status.PAID:
        raise ValidationError("Paid orders cannot be cancelled from this action")
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    CardSecret.objects.filter(reserved_order=order, status=CardSecret.Status.RESERVED).update(
        status=CardSecret.Status.AVAILABLE,
        reserved_order=None,
        reserved_until=None,
    )
    order.refresh_from_db()
    return order, before, order_snapshot(order)


@transaction.atomic
def admin_release_stock(order_id):
    order = Order.objects.select_for_update().get(id=order_id)
    before = order_snapshot(order)
    if order.status != Order.Status.PENDING:
        raise ValidationError("Only pending orders can release stock")
    order.status = Order.Status.EXPIRED
    order.save(update_fields=["status", "updated_at"])
    CardSecret.objects.filter(reserved_order=order, status=CardSecret.Status.RESERVED).update(
        status=CardSecret.Status.AVAILABLE,
        reserved_order=None,
        reserved_until=None,
    )
    order.refresh_from_db()
    return order, before, order_snapshot(order)


def admin_redeliver_order(order_id):
    order = Order.objects.get(id=order_id)
    if order.status != Order.Status.PAID:
        raise ValidationError("Only paid orders can be redelivered")
    return order, order_snapshot(order), order_snapshot(order)


@transaction.atomic
def admin_replace_card(order_id):
    order = Order.objects.select_for_update().select_related("product").get(id=order_id)
    before = order_snapshot(order)
    if order.status != Order.Status.PAID:
        raise ValidationError("Only paid orders can replace cards")
    old_cards = list(CardSecret.objects.select_for_update().filter(reserved_order=order, status=CardSecret.Status.SOLD))
    new_cards = list(
        CardSecret.objects.select_for_update()
        .filter(product=order.product, status=CardSecret.Status.AVAILABLE)
        .order_by("id")[: order.quantity]
    )
    if len(new_cards) < order.quantity:
        raise ValidationError("Insufficient available stock for replacement")
    now = timezone.now()
    for card in old_cards:
        card.status = CardSecret.Status.VOID
        card.reserved_until = None
    for card in new_cards:
        card.status = CardSecret.Status.SOLD
        card.reserved_order = order
        card.reserved_until = None
        card.sold_at = now
    CardSecret.objects.bulk_update(old_cards + new_cards, ["status", "reserved_order", "reserved_until", "sold_at"])
    order.delivery_items = [card.get_secret() for card in new_cards]
    order.delivered_at = now
    order.save(update_fields=["delivery_items", "delivered_at", "updated_at"])
    order.refresh_from_db()
    return order, before, order_snapshot(order)


@transaction.atomic
def resolve_payment_exception(payment_id, reason):
    from orders.models import PaymentTransaction

    payment = PaymentTransaction.objects.select_for_update().select_related("order").get(id=payment_id)
    before = {
        "status": payment.status,
        "note": payment.note,
    }
    payment.status = PaymentTransaction.Status.IGNORED
    payment.note = reason
    payment.save(update_fields=["status", "note"])
    after = {
        "status": payment.status,
        "note": payment.note,
    }
    return payment, before, after
```

- [ ] **Step 4: Add action views**

Append to `backend/admin_console/views.py`:

```python
from django.core.exceptions import ValidationError as DjangoValidationError

from .order_actions import (
    admin_cancel_order,
    admin_mark_paid,
    admin_redeliver_order,
    admin_release_stock,
    admin_replace_card,
    resolve_payment_exception,
)


class ReasonSerializer(drf_serializers.Serializer):
    reason = drf_serializers.CharField()


class OrderActionView(RequirePermissionMixin, APIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_orders"
    action_name = ""
    service = None

    def post(self, request, order_id):
        self.check_permissions(request)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"].strip()
        if not reason:
            raise ValidationError({"detail": "Reason is required"})
        try:
            order, before, after = self.service(order_id)
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages[0]}) from exc
        log = record_operation(
            request=request,
            action=self.action_name,
            target=order,
            reason=reason,
            before=before,
            after=after,
        )
        data = OrderAdminSerializer(order).data
        data["log_id"] = log.id
        return Response(data)


class MarkPaidView(OrderActionView):
    action_name = "order.mark_paid"
    service = staticmethod(admin_mark_paid)


class CancelOrderView(OrderActionView):
    action_name = "order.cancel"
    service = staticmethod(admin_cancel_order)


class RedeliverOrderView(OrderActionView):
    action_name = "order.redeliver"
    service = staticmethod(admin_redeliver_order)


class ReplaceCardView(OrderActionView):
    action_name = "order.replace_card"
    service = staticmethod(admin_replace_card)


class ReleaseStockView(OrderActionView):
    action_name = "order.release_stock"
    service = staticmethod(admin_release_stock)


class PaymentResolveView(RequirePermissionMixin, APIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_resolve_payments"

    def post(self, request, payment_id):
        self.check_permissions(request)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"].strip()
        if not reason:
            raise ValidationError({"detail": "Reason is required"})
        try:
            payment, before, after = resolve_payment_exception(payment_id, reason)
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages[0]}) from exc
        log = record_operation(
            request=request,
            action="payment.resolve",
            target=payment,
            reason=reason,
            before=before,
            after=after,
        )
        data = PaymentAdminSerializer(payment, context={"can_view_sensitive_payload": True}).data
        data["log_id"] = log.id
        return Response(data)
```

Add URL paths:

```python
    path("orders/<int:order_id>/mark-paid", MarkPaidView.as_view()),
    path("orders/<int:order_id>/cancel", CancelOrderView.as_view()),
    path("orders/<int:order_id>/redeliver", RedeliverOrderView.as_view()),
    path("orders/<int:order_id>/replace-card", ReplaceCardView.as_view()),
    path("orders/<int:order_id>/release-stock", ReleaseStockView.as_view()),
    path("payments/<int:payment_id>/resolve", PaymentResolveView.as_view()),
```

- [ ] **Step 5: Run tests**

Run:

```powershell
cd backend
uv run pytest tests/test_admin_console_order_actions.py tests/test_order_flow.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/admin_console backend/tests/test_admin_console_order_actions.py
git commit -m "feat: add admin console order actions"
```

## Task 5: Users, Content, Settings, Logs, And Updates

**Files:**

- Modify: `backend/admin_console/serializers.py`
- Modify: `backend/admin_console/views.py`
- Modify: `backend/admin_console/urls.py`
- Test: `backend/tests/test_admin_console_users_content.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin_console_users_content.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from admin_console.models import AdminOperationLog, AdminProfile
from shop.models import Announcement, SiteConfig


class AdminConsoleUsersContentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="Password123!",
        )
        self.operator = User.objects.create_user(
            username="operator@example.com",
            email="operator@example.com",
            password="Password123!",
            is_staff=True,
        )
        AdminProfile.objects.create(user=self.operator, role=AdminProfile.Role.OPERATOR)
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_superadmin_can_assign_staff_role(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/admin-console/users/{self.operator.id}",
            {"role": "finance", "is_staff": True, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.admin_profile.role, "finance")

    def test_operator_cannot_assign_staff_role(self):
        self.authenticate(self.operator)

        response = self.client.patch(
            f"/api/admin-console/users/{self.operator.id}",
            {"role": "finance", "is_staff": True, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_operator_can_create_announcement(self):
        self.authenticate(self.operator)

        response = self.client.post(
            "/api/admin-console/announcements",
            {"title": "Maintenance", "content": "Tonight", "is_active": True, "sort_order": 0},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Announcement.objects.get().title, "Maintenance")

    def test_superadmin_can_update_site_config(self):
        self.authenticate(self.superadmin)
        SiteConfig.objects.create(key="site_name", label="Site name", value="Old")

        response = self.client.patch(
            "/api/admin-console/site-config/site_name",
            {"label": "Site name", "value": "New"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SiteConfig.objects.get(key="site_name").value, "New")

    def test_logs_endpoint_returns_operation_logs(self):
        self.authenticate(self.superadmin)
        AdminOperationLog.objects.create(
            actor=self.operator,
            actor_email=self.operator.email,
            actor_role="operator",
            action="inventory.import",
            target_type="Product",
            target_id="1",
            reason="Restock",
        )

        response = self.client.get("/api/admin-console/logs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["action"], "inventory.import")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
cd backend
uv run pytest tests/test_admin_console_users_content.py -q
```

Expected: FAIL with `404` for user/content/log endpoints.

- [ ] **Step 3: Add serializers**

Append to `backend/admin_console/serializers.py`:

```python
from .models import AdminOperationLog, AdminProfile


class UserAdminSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    order_count = serializers.IntegerField(read_only=True, default=0)
    total_paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, default=0)

    class Meta:
        model = get_user_model()
        fields = ["id", "email", "username", "is_active", "is_staff", "is_superuser", "role", "order_count", "total_paid_amount"]

    def get_role(self, obj):
        return get_admin_role(obj)


class UserAdminUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()
    is_staff = serializers.BooleanField()
    role = serializers.ChoiceField(choices=AdminProfile.Role.choices)


class SiteConfigUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(required=False, allow_blank=True)
    value = serializers.CharField(allow_blank=True)


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
```

- [ ] **Step 4: Add views and URL paths**

Append to `backend/admin_console/views.py`:

```python
from django.db.models import Count, Sum

from .models import AdminOperationLog, AdminProfile
from .serializers import (
    AdminOperationLogSerializer,
    AnnouncementAdminSerializer,
    SiteConfigAdminSerializer,
    SiteConfigUpdateSerializer,
    UserAdminSerializer,
    UserAdminUpdateSerializer,
)
from shop.models import Announcement, SiteConfig


class UserListView(RequirePermissionMixin, generics.ListAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_users"
    serializer_class = UserAdminSerializer

    def get_queryset(self):
        User = get_user_model()
        queryset = User.objects.annotate(order_count=Count("order"), total_paid_amount=Sum("order__amount")).order_by("-date_joined")
        keyword = self.request.query_params.get("keyword", "").strip()
        if keyword:
            queryset = queryset.filter(email__icontains=keyword)
        return queryset


class UserDetailView(RequirePermissionMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_staff"
    serializer_class = UserAdminSerializer
    queryset = get_user_model().objects.all()

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserAdminUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        before = {"is_active": user.is_active, "is_staff": user.is_staff, "role": get_admin_role(user)}
        user.is_active = serializer.validated_data["is_active"]
        user.is_staff = serializer.validated_data["is_staff"]
        user.save(update_fields=["is_active", "is_staff"])
        AdminProfile.objects.update_or_create(user=user, defaults={"role": serializer.validated_data["role"]})
        after = {"is_active": user.is_active, "is_staff": user.is_staff, "role": get_admin_role(user)}
        record_operation(request=request, action="user.update_staff", target=user, reason="Staff role update", before=before, after=after)
        return Response(UserAdminSerializer(user).data)


class AnnouncementListCreateView(RequirePermissionMixin, generics.ListCreateAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_products"
    serializer_class = AnnouncementAdminSerializer
    queryset = Announcement.objects.order_by("sort_order", "-created_at")


class AnnouncementDetailView(RequirePermissionMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_products"
    serializer_class = AnnouncementAdminSerializer
    queryset = Announcement.objects.all()


class SiteConfigListView(RequirePermissionMixin, generics.ListAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_settings"
    serializer_class = SiteConfigAdminSerializer
    queryset = SiteConfig.objects.order_by("key")


class SiteConfigDetailView(RequirePermissionMixin, APIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_manage_settings"

    def patch(self, request, key):
        self.check_permissions(request)
        serializer = SiteConfigUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item, _created = SiteConfig.objects.get_or_create(key=key, defaults={"label": key, "value": ""})
        before = {"label": item.label, "value": item.value}
        item.label = serializer.validated_data.get("label", item.label)
        item.value = serializer.validated_data["value"]
        item.save(update_fields=["label", "value"])
        after = {"label": item.label, "value": item.value}
        record_operation(request=request, action="site_config.update", target=item, reason=f"Update {key}", before=before, after=after)
        return Response(SiteConfigAdminSerializer(item).data)


class OperationLogListView(RequirePermissionMixin, generics.ListAPIView):
    permission_classes = [IsAdminConsoleUser]
    required_permission = "can_view_logs"
    serializer_class = AdminOperationLogSerializer
    queryset = AdminOperationLog.objects.order_by("-created_at", "-id")
```

Add URL paths:

```python
    path("users", UserListView.as_view()),
    path("users/<int:pk>", UserDetailView.as_view()),
    path("announcements", AnnouncementListCreateView.as_view()),
    path("announcements/<int:pk>", AnnouncementDetailView.as_view()),
    path("site-config", SiteConfigListView.as_view()),
    path("site-config/<str:key>", SiteConfigDetailView.as_view()),
    path("logs", OperationLogListView.as_view()),
```

- [ ] **Step 5: Run backend suite**

Run:

```powershell
cd backend
uv run pytest -q
uv run python manage.py check
```

Expected: all tests PASS and Django check reports no issues.

- [ ] **Step 6: Commit**

```powershell
git add backend/admin_console backend/tests/test_admin_console_users_content.py
git commit -m "feat: add admin console users content and logs"
```

## Task 6: Frontend Admin API, Session Store, Permissions, And Routes

**Files:**

- Modify: `frontend/package.json`
- Create: `frontend/src/api/adminConsole.js`
- Create: `frontend/src/admin/permissions.js`
- Create: `frontend/src/admin/permissions.spec.js`
- Create: `frontend/src/stores/adminSession.js`
- Create: `frontend/src/stores/adminSession.spec.js`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: Add frontend test harness**

Modify `frontend/package.json` scripts and dev dependencies:

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0",
    "test:unit": "vitest run"
  },
  "devDependencies": {
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^24.1.3",
    "vitest": "^2.1.9"
  }
}
```

Run:

```powershell
cd frontend
npm install
```

Expected: lockfile updates with Vitest dependencies.

- [ ] **Step 2: Write failing permission helper test**

Create `frontend/src/admin/permissions.spec.js`:

```javascript
import { describe, expect, it } from 'vitest'

import { adminMenusForSession, canUseAdminAction } from './permissions'

describe('admin permissions', () => {
  it('shows operator operations menus but hides finance and staff menus', () => {
    const session = {
      role: 'operator',
      permissions: {
        can_manage_orders: true,
        can_manage_products: true,
        can_manage_inventory: true,
        can_view_payments: false,
        can_manage_users: false,
        can_view_logs: true,
      },
    }

    const keys = adminMenusForSession(session).map((item) => item.key)

    expect(keys).toContain('orders')
    expect(keys).toContain('inventory')
    expect(keys).not.toContain('payments')
    expect(keys).not.toContain('users')
    expect(canUseAdminAction(session, 'can_manage_inventory')).toBe(true)
  })
})
```

- [ ] **Step 3: Run permission test to verify it fails**

Run:

```powershell
cd frontend
npm run test:unit -- src/admin/permissions.spec.js
```

Expected: FAIL with `Failed to resolve import "./permissions"`.

- [ ] **Step 4: Implement permission helper**

Create `frontend/src/admin/permissions.js`:

```javascript
import {
  Box,
  CreditCard,
  DataAnalysis,
  Document,
  Goods,
  List,
  Setting,
  Tickets,
  User,
} from '@element-plus/icons-vue'

export const ADMIN_MENUS = [
  { key: 'dashboard', label: '工作台', path: '/admin-console', icon: DataAnalysis, permission: 'can_view_dashboard' },
  { key: 'orders', label: '订单管理', path: '/admin-console/orders', icon: Tickets, permission: 'can_manage_orders' },
  { key: 'products', label: '商品管理', path: '/admin-console/products', icon: Goods, permission: 'can_manage_products' },
  { key: 'inventory', label: '库存管理', path: '/admin-console/inventory', icon: Box, permission: 'can_manage_inventory' },
  { key: 'payments', label: '支付流水', path: '/admin-console/payments', icon: CreditCard, permission: 'can_view_payments' },
  { key: 'users', label: '用户管理', path: '/admin-console/users', icon: User, permission: 'can_manage_users' },
  { key: 'content', label: '内容配置', path: '/admin-console/content', icon: Setting, permission: 'can_manage_products' },
  { key: 'logs', label: '操作日志', path: '/admin-console/logs', icon: Document, permission: 'can_view_logs' },
]

export const canUseAdminAction = (session, permission) => Boolean(session?.permissions?.[permission])

export const adminMenusForSession = (session) =>
  ADMIN_MENUS.filter((item) => canUseAdminAction(session, item.permission))
```

- [ ] **Step 5: Write failing admin session store test**

Create `frontend/src/stores/adminSession.spec.js`:

```javascript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../api/adminConsole', () => ({
  fetchAdminMe: vi.fn(async () => ({
    id: 1,
    email: 'operator@example.com',
    role: 'operator',
    permissions: { can_manage_orders: true },
  })),
}))

import { fetchAdminMe } from '../api/adminConsole'
import { useAdminSessionStore } from './adminSession'

describe('admin session store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads admin identity once and stores permissions', async () => {
    const store = useAdminSessionStore()

    await store.load()

    expect(fetchAdminMe).toHaveBeenCalledTimes(1)
    expect(store.user.email).toBe('operator@example.com')
    expect(store.role).toBe('operator')
    expect(store.permissions.can_manage_orders).toBe(true)
  })
})
```

- [ ] **Step 6: Run admin session test to verify it fails**

Run:

```powershell
cd frontend
npm run test:unit -- src/stores/adminSession.spec.js
```

Expected: FAIL with `Failed to resolve import "./adminSession"`.

- [ ] **Step 7: Implement admin API and session store**

Create `frontend/src/api/adminConsole.js`:

```javascript
import { api } from './client'

export const fetchAdminMe = () => api.get('/admin-console/me').then((res) => res.data)
export const fetchAdminDashboard = () => api.get('/admin-console/dashboard').then((res) => res.data)
export const fetchAdminProducts = (params = {}) => api.get('/admin-console/products', { params }).then((res) => res.data)
export const createAdminProduct = (payload) => api.post('/admin-console/products', payload).then((res) => res.data)
export const updateAdminProduct = (id, payload) => api.patch(`/admin-console/products/${id}`, payload).then((res) => res.data)
export const fetchAdminCategories = (params = {}) => api.get('/admin-console/categories', { params }).then((res) => res.data)
export const createAdminCategory = (payload) => api.post('/admin-console/categories', payload).then((res) => res.data)
export const updateAdminCategory = (id, payload) => api.patch(`/admin-console/categories/${id}`, payload).then((res) => res.data)
export const fetchAdminCards = (params = {}) => api.get('/admin-console/cards', { params }).then((res) => res.data)
export const fetchAdminOrders = (params = {}) => api.get('/admin-console/orders', { params }).then((res) => res.data)
export const fetchAdminPayments = (params = {}) => api.get('/admin-console/payments', { params }).then((res) => res.data)
export const fetchAdminPayment = (id) => api.get(`/admin-console/payments/${id}`).then((res) => res.data)
export const resolveAdminPayment = (id, payload) => api.post(`/admin-console/payments/${id}/resolve`, payload).then((res) => res.data)
export const previewCardImport = (payload) => api.post('/admin-console/cards/import/preview', payload).then((res) => res.data)
export const commitCardImport = (payload) => api.post('/admin-console/cards/import/commit', payload).then((res) => res.data)
export const markAdminOrderPaid = (id, payload) => api.post(`/admin-console/orders/${id}/mark-paid`, payload).then((res) => res.data)
export const cancelAdminOrder = (id, payload) => api.post(`/admin-console/orders/${id}/cancel`, payload).then((res) => res.data)
export const redeliverAdminOrder = (id, payload) => api.post(`/admin-console/orders/${id}/redeliver`, payload).then((res) => res.data)
export const replaceAdminOrderCard = (id, payload) => api.post(`/admin-console/orders/${id}/replace-card`, payload).then((res) => res.data)
export const releaseAdminOrderStock = (id, payload) => api.post(`/admin-console/orders/${id}/release-stock`, payload).then((res) => res.data)
export const fetchAdminUsers = (params = {}) => api.get('/admin-console/users', { params }).then((res) => res.data)
export const updateAdminUser = (id, payload) => api.patch(`/admin-console/users/${id}`, payload).then((res) => res.data)
export const fetchAdminAnnouncements = () => api.get('/admin-console/announcements').then((res) => res.data)
export const createAdminAnnouncement = (payload) => api.post('/admin-console/announcements', payload).then((res) => res.data)
export const updateAdminAnnouncement = (id, payload) => api.patch(`/admin-console/announcements/${id}`, payload).then((res) => res.data)
export const fetchAdminSiteConfig = () => api.get('/admin-console/site-config').then((res) => res.data)
export const updateAdminSiteConfig = (key, payload) => api.patch(`/admin-console/site-config/${key}`, payload).then((res) => res.data)
export const fetchAdminLogs = (params = {}) => api.get('/admin-console/logs', { params }).then((res) => res.data)
```

Create `frontend/src/stores/adminSession.js`:

```javascript
import { defineStore } from 'pinia'

import { fetchAdminMe } from '../api/adminConsole'

export const useAdminSessionStore = defineStore('adminSession', {
  state: () => ({
    loaded: false,
    loading: false,
    user: null,
    role: '',
    permissions: {},
  }),
  actions: {
    async load({ force = false } = {}) {
      if (this.loaded && !force) return
      this.loading = true
      try {
        const data = await fetchAdminMe()
        this.user = data
        this.role = data.role
        this.permissions = data.permissions || {}
        this.loaded = true
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.loaded = false
      this.loading = false
      this.user = null
      this.role = ''
      this.permissions = {}
    },
  },
})
```

- [ ] **Step 8: Add admin routes and guards**

Modify `frontend/src/router/index.js` with admin imports and routes:

```javascript
import AdminConsoleLayout from '../views/admin/AdminConsoleLayout.vue'
import AdminForbiddenView from '../views/admin/AdminForbiddenView.vue'
import AdminDashboardView from '../views/admin/DashboardView.vue'
import AdminOrdersView from '../views/admin/OrdersView.vue'
import AdminProductsView from '../views/admin/ProductsView.vue'
import AdminInventoryView from '../views/admin/InventoryView.vue'
import AdminPaymentsView from '../views/admin/PaymentsView.vue'
import AdminUsersView from '../views/admin/UsersView.vue'
import AdminContentView from '../views/admin/ContentView.vue'
import AdminLogsView from '../views/admin/LogsView.vue'
import { useAdminSessionStore } from '../stores/adminSession'
```

Add route records:

```javascript
    {
      path: '/admin-console',
      component: AdminConsoleLayout,
      meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        { path: '', name: 'admin-dashboard', component: AdminDashboardView },
        { path: 'orders', name: 'admin-orders', component: AdminOrdersView },
        { path: 'products', name: 'admin-products', component: AdminProductsView },
        { path: 'inventory', name: 'admin-inventory', component: AdminInventoryView },
        { path: 'payments', name: 'admin-payments', component: AdminPaymentsView },
        { path: 'users', name: 'admin-users', component: AdminUsersView },
        { path: 'content', name: 'admin-content', component: AdminContentView },
        { path: 'logs', name: 'admin-logs', component: AdminLogsView },
      ],
    },
    { path: '/admin-console/forbidden', name: 'admin-forbidden', component: AdminForbiddenView },
```

Update `beforeEach`:

```javascript
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('access_token')) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin) {
    const adminSession = useAdminSessionStore()
    try {
      await adminSession.load()
    } catch {
      return { path: '/admin-console/forbidden' }
    }
  }
  return true
})
```

- [ ] **Step 9: Run frontend helper tests**

Run:

```powershell
cd frontend
npm run test:unit -- src/admin/permissions.spec.js src/stores/adminSession.spec.js
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/src/api/adminConsole.js frontend/src/admin frontend/src/stores/adminSession.js frontend/src/stores/adminSession.spec.js frontend/src/router/index.js
git commit -m "feat: add admin console frontend session"
```

## Task 7: Vue Admin Layout And Pages

**Files:**

- Create: `frontend/src/views/admin/AdminConsoleLayout.vue`
- Create: `frontend/src/views/admin/AdminForbiddenView.vue`
- Create: `frontend/src/views/admin/DashboardView.vue`
- Create: `frontend/src/views/admin/OrdersView.vue`
- Create: `frontend/src/views/admin/ProductsView.vue`
- Create: `frontend/src/views/admin/InventoryView.vue`
- Create: `frontend/src/views/admin/PaymentsView.vue`
- Create: `frontend/src/views/admin/UsersView.vue`
- Create: `frontend/src/views/admin/ContentView.vue`
- Create: `frontend/src/views/admin/LogsView.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Run build to verify route imports fail before pages exist**

Run:

```powershell
cd frontend
npm run build
```

Expected: FAIL with missing admin view imports.

- [ ] **Step 2: Create admin layout**

Create `frontend/src/views/admin/AdminConsoleLayout.vue`:

```vue
<template>
  <div class="admin-console">
    <aside class="admin-sidebar">
      <RouterLink class="admin-brand" to="/admin-console">
        <span class="brand-mark">AI</span>
        <span>运营后台</span>
      </RouterLink>
      <nav class="admin-menu">
        <RouterLink v-for="item in menus" :key="item.key" :to="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>
    <section class="admin-main">
      <header class="admin-header">
        <div>
          <strong>{{ admin.user?.email }}</strong>
          <span>{{ admin.role }}</span>
        </div>
        <el-button :icon="Refresh" @click="admin.load({ force: true })">刷新权限</el-button>
      </header>
      <RouterView />
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'

import { adminMenusForSession } from '../../admin/permissions'
import { useAdminSessionStore } from '../../stores/adminSession'

const admin = useAdminSessionStore()
const menus = computed(() => adminMenusForSession(admin))
</script>
```

- [ ] **Step 3: Create forbidden page**

Create `frontend/src/views/admin/AdminForbiddenView.vue`:

```vue
<template>
  <main class="page narrow">
    <el-empty description="当前账号没有后台权限">
      <el-button type="primary" @click="$router.push('/login?redirect=/admin-console')">重新登录</el-button>
    </el-empty>
  </main>
</template>
```

- [ ] **Step 4: Create dashboard page**

Create `frontend/src/views/admin/DashboardView.vue` with these sections:

```vue
<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>工作台</h1>
        <p>今日经营、待办和趋势</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>
    <section class="admin-metrics">
      <article v-for="item in metricItems" :key="item.label" class="admin-metric">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </section>
    <section class="admin-grid two">
      <div class="admin-panel">
        <h2>低库存</h2>
        <el-table :data="dashboard.low_stock_products || []" size="small">
          <el-table-column prop="name" label="商品" />
          <el-table-column prop="available_stock" label="库存" width="90" />
        </el-table>
      </div>
      <div class="admin-panel">
        <h2>商品排行</h2>
        <el-table :data="dashboard.top_products || []" size="small">
          <el-table-column prop="name" label="商品" />
          <el-table-column prop="paid_amount" label="成交额" width="120" />
        </el-table>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { fetchAdminDashboard } from '../../api/adminConsole'

const loading = ref(false)
const dashboard = ref({ summary: {} })
const metricItems = computed(() => [
  { label: '今日订单', value: dashboard.value.summary?.today_order_count ?? 0 },
  { label: '今日成交', value: `¥${dashboard.value.summary?.today_paid_amount ?? '0.00'}` },
  { label: '待支付订单', value: dashboard.value.summary?.pending_order_count ?? 0 },
  { label: '低库存商品', value: dashboard.value.summary?.low_stock_product_count ?? 0 },
  { label: '异常支付', value: dashboard.value.summary?.abnormal_payment_count ?? 0 },
])

const load = async () => {
  loading.value = true
  try {
    dashboard.value = await fetchAdminDashboard()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
```

- [ ] **Step 5: Create orders page**

Create `frontend/src/views/admin/OrdersView.vue`:

```vue
<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div><h1>Orders</h1><p>Search, inspect, and intervene in order delivery.</p></div>
      <el-button :icon="Refresh" @click="load">Refresh</el-button>
    </div>
    <div class="admin-panel admin-toolbar">
      <el-input v-model="filters.keyword" clearable placeholder="Order no or contact" @keyup.enter="load" />
      <el-select v-model="filters.status" clearable placeholder="Status">
        <el-option label="Pending" value="pending" />
        <el-option label="Paid" value="paid" />
        <el-option label="Expired" value="expired" />
        <el-option label="Cancelled" value="cancelled" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="load">Search</el-button>
    </div>
    <el-table :data="orders" size="small" class="admin-table">
      <el-table-column prop="order_no" label="Order no" min-width="170" />
      <el-table-column prop="product_name" label="Product" min-width="160" />
      <el-table-column prop="contact" label="Contact" min-width="180" />
      <el-table-column prop="amount" label="Amount" width="110" />
      <el-table-column prop="status" label="Status" width="110" />
      <el-table-column label="Actions" width="360" fixed="right">
        <template #default="{ row }">
          <el-button size="small" :icon="CircleCheck" @click="runOrderAction(row, markAdminOrderPaid)">Paid</el-button>
          <el-button size="small" :icon="Close" @click="runOrderAction(row, cancelAdminOrder)">Cancel</el-button>
          <el-button size="small" :icon="Tickets" @click="runOrderAction(row, redeliverAdminOrder)">Redeliver</el-button>
          <el-button size="small" :icon="RefreshRight" @click="runOrderAction(row, replaceAdminOrderCard)">Replace</el-button>
          <el-button size="small" :icon="Box" @click="runOrderAction(row, releaseAdminOrderStock)">Release</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !orders.length" description="No orders" />
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, CircleCheck, Close, Refresh, RefreshRight, Search, Tickets } from '@element-plus/icons-vue'

import {
  cancelAdminOrder,
  fetchAdminOrders,
  markAdminOrderPaid,
  redeliverAdminOrder,
  releaseAdminOrderStock,
  replaceAdminOrderCard,
} from '../../api/adminConsole'

const loading = ref(false)
const orders = ref([])
const filters = reactive({ keyword: '', status: '' })

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminOrders(filters)
    orders.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

const runOrderAction = async (order, action) => {
  const { value } = await ElMessageBox.prompt('Reason is required', `Order ${order.order_no}`, {
    confirmButtonText: 'Submit',
    cancelButtonText: 'Cancel',
    inputType: 'textarea',
    inputValidator: (text) => Boolean(text && text.trim()),
    inputErrorMessage: 'Reason is required',
  })
  await action(order.id, { reason: value.trim() })
  ElMessage.success('Operation recorded')
  await load()
}

onMounted(load)
</script>
```

- [ ] **Step 6: Create products page**

Create `frontend/src/views/admin/ProductsView.vue`:

```vue
<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div><h1>Products</h1><p>Manage catalog status and stock overview.</p></div>
      <el-button :icon="Refresh" @click="load">Refresh</el-button>
    </div>
    <el-table :data="products" size="small" class="admin-table">
      <el-table-column prop="name" label="Name" min-width="180" />
      <el-table-column prop="category_name" label="Category" width="140" />
      <el-table-column prop="price" label="Price" width="100" />
      <el-table-column label="Stock" width="220">
        <template #default="{ row }">
          Available {{ row.stock?.available || 0 }} / Reserved {{ row.stock?.reserved || 0 }} / Sold {{ row.stock?.sold || 0 }}
        </template>
      </el-table-column>
      <el-table-column label="Active" width="110">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" @change="updateAdminProduct(row.id, { is_active: row.is_active }).then(load)" />
        </template>
      </el-table-column>
      <el-table-column label="Sort" width="110">
        <template #default="{ row }">
          <el-input-number v-model="row.sort_order" size="small" :min="0" @change="updateAdminProduct(row.id, { sort_order: row.sort_order }).then(load)" />
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !products.length" description="No products" />
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { fetchAdminProducts, updateAdminProduct } from '../../api/adminConsole'

const loading = ref(false)
const products = ref([])

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminProducts()
    products.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
```

- [ ] **Step 7: Create inventory page**

Create `frontend/src/views/admin/InventoryView.vue`:

```vue
<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div><h1>Inventory</h1><p>Preview and commit card imports.</p></div>
      <el-button :icon="Refresh" @click="load">Refresh</el-button>
    </div>
    <section class="admin-grid two">
      <div class="admin-panel">
        <h2>Import cards</h2>
        <el-form label-position="top">
          <el-form-item label="Product">
            <el-select v-model="form.product_id" filterable placeholder="Select product">
              <el-option v-for="product in products" :key="product.id" :label="product.name" :value="product.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="Cards">
            <el-input v-model="form.cards" type="textarea" :rows="12" placeholder="One card per line" />
          </el-form-item>
          <el-form-item label="Reason">
            <el-input v-model="form.reason" placeholder="Restock reason" />
          </el-form-item>
          <el-button :icon="Search" @click="preview">Preview</el-button>
          <el-button type="primary" :disabled="!previewResult" @click="commit">Commit</el-button>
        </el-form>
      </div>
      <div class="admin-panel">
        <h2>Preview</h2>
        <el-descriptions v-if="previewResult" :column="1" border>
          <el-descriptions-item label="Total">{{ previewResult.total_rows }}</el-descriptions-item>
          <el-descriptions-item label="Valid">{{ previewResult.valid_count }}</el-descriptions-item>
          <el-descriptions-item label="Empty">{{ previewResult.empty_count }}</el-descriptions-item>
          <el-descriptions-item label="Batch duplicate">{{ previewResult.same_batch_duplicate_count }}</el-descriptions-item>
          <el-descriptions-item label="Existing duplicate">{{ previewResult.existing_duplicate_count }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="No preview" />
      </div>
    </section>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'

import { commitCardImport, fetchAdminProducts, previewCardImport } from '../../api/adminConsole'

const loading = ref(false)
const products = ref([])
const previewResult = ref(null)
const form = reactive({ product_id: '', cards: '', reason: '' })

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminProducts()
    products.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

const preview = async () => {
  previewResult.value = await previewCardImport({ product_id: form.product_id, cards: form.cards })
}

const commit = async () => {
  await commitCardImport({ product_id: form.product_id, cards: form.cards, reason: form.reason })
  ElMessage.success('Cards imported')
  previewResult.value = null
  form.cards = ''
  await load()
}

onMounted(load)
</script>
```

- [ ] **Step 8: Create payments page**

Create `frontend/src/views/admin/PaymentsView.vue`:

```vue
<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div><h1>Payments</h1><p>Inspect transactions and resolve exceptions.</p></div>
      <el-button :icon="Refresh" @click="load">Refresh</el-button>
    </div>
    <el-table :data="payments" size="small" class="admin-table">
      <el-table-column prop="provider" label="Provider" width="110" />
      <el-table-column prop="out_trade_no" label="Order no" min-width="170" />
      <el-table-column prop="trade_no" label="Trade no" min-width="150" />
      <el-table-column prop="amount" label="Amount" width="100" />
      <el-table-column prop="status" label="Status" width="110" />
      <el-table-column label="Actions" width="180">
        <template #default="{ row }">
          <el-button size="small" :icon="View" @click="selected = row">Payload</el-button>
          <el-button size="small" :icon="CircleCheck" @click="resolve(row)">Resolve</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-drawer v-model="payloadOpen" title="Payload" size="520px" @closed="selected = null">
      <pre>{{ JSON.stringify(selected?.raw_payload || {}, null, 2) }}</pre>
    </el-drawer>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, Refresh, View } from '@element-plus/icons-vue'

import { fetchAdminPayments, resolveAdminPayment } from '../../api/adminConsole'

const loading = ref(false)
const payments = ref([])
const selected = ref(null)
const payloadOpen = computed({
  get: () => Boolean(selected.value),
  set: (value) => {
    if (!value) selected.value = null
  },
})

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminPayments()
    payments.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

const resolve = async (payment) => {
  const { value } = await ElMessageBox.prompt('Reason is required', 'Resolve payment', {
    inputType: 'textarea',
    inputValidator: (text) => Boolean(text && text.trim()),
  })
  await resolveAdminPayment(payment.id, { reason: value.trim() })
  ElMessage.success('Payment resolved')
  await load()
}

onMounted(load)
</script>
```

- [ ] **Step 9: Create users page**

Create `frontend/src/views/admin/UsersView.vue`:

```vue
<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div><h1>Users</h1><p>Manage staff access and account status.</p></div>
      <el-button :icon="Refresh" @click="load">Refresh</el-button>
    </div>
    <el-table :data="users" size="small" class="admin-table">
      <el-table-column prop="email" label="Email" min-width="200" />
      <el-table-column prop="role" label="Role" width="130" />
      <el-table-column prop="order_count" label="Orders" width="100" />
      <el-table-column prop="total_paid_amount" label="Paid amount" width="130" />
      <el-table-column label="Active" width="100">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" :disabled="!canManageStaff" @change="save(row)" />
        </template>
      </el-table-column>
      <el-table-column label="Staff role" width="180">
        <template #default="{ row }">
          <el-select v-model="row.role" :disabled="!canManageStaff" @change="save(row)">
            <el-option label="Operator" value="operator" />
            <el-option label="Finance" value="finance" />
            <el-option label="Super Admin" value="superadmin" />
          </el-select>
        </template>
      </el-table-column>
    </el-table>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { fetchAdminUsers, updateAdminUser } from '../../api/adminConsole'
import { useAdminSessionStore } from '../../stores/adminSession'

const admin = useAdminSessionStore()
const loading = ref(false)
const users = ref([])
const canManageStaff = computed(() => Boolean(admin.permissions.can_manage_staff))

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminUsers()
    users.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

const save = async (user) => {
  await updateAdminUser(user.id, { is_active: user.is_active, is_staff: user.is_staff, role: user.role })
  ElMessage.success('User updated')
}

onMounted(load)
</script>
```

- [ ] **Step 10: Create content and logs pages**

Create `frontend/src/views/admin/ContentView.vue`:

```vue
<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div><h1>Content</h1><p>Announcements and site config.</p></div>
      <el-button :icon="Refresh" @click="load">Refresh</el-button>
    </div>
    <section class="admin-grid two">
      <div class="admin-panel">
        <h2>Announcements</h2>
        <el-table :data="announcements" size="small">
          <el-table-column prop="title" label="Title" />
          <el-table-column prop="is_active" label="Active" width="90" />
        </el-table>
      </div>
      <div class="admin-panel">
        <h2>Site config</h2>
        <el-table :data="configs" size="small">
          <el-table-column prop="key" label="Key" width="140" />
          <el-table-column prop="value" label="Value" />
        </el-table>
      </div>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { fetchAdminAnnouncements, fetchAdminSiteConfig } from '../../api/adminConsole'

const loading = ref(false)
const announcements = ref([])
const configs = ref([])

const load = async () => {
  loading.value = true
  try {
    const [announcementResponse, configResponse] = await Promise.all([
      fetchAdminAnnouncements(),
      fetchAdminSiteConfig(),
    ])
    announcements.value = announcementResponse.results || []
    configs.value = configResponse.results || []
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
```

Create `frontend/src/views/admin/LogsView.vue`:

```vue
<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div><h1>Operation Logs</h1><p>Audit trail for staff actions.</p></div>
      <el-button :icon="Refresh" @click="load">Refresh</el-button>
    </div>
    <el-table :data="logs" size="small" class="admin-table">
      <el-table-column prop="created_at" label="Time" width="180" />
      <el-table-column prop="actor_email" label="Actor" min-width="180" />
      <el-table-column prop="action" label="Action" min-width="160" />
      <el-table-column prop="target_type" label="Target" width="120" />
      <el-table-column prop="target_id" label="Target ID" width="100" />
      <el-table-column prop="reason" label="Reason" min-width="220" />
    </el-table>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { fetchAdminLogs } from '../../api/adminConsole'

const loading = ref(false)
const logs = ref([])

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminLogs()
    logs.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
```

- [ ] **Step 11: Add admin styles**

Append to `frontend/src/styles/main.css`:

```css
.admin-console {
  display: grid;
  grid-template-columns: 232px 1fr;
  min-height: 100vh;
  background: #f6f8fb;
  color: #1f2937;
}

.admin-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 16px 12px;
  border-right: 1px solid #dfe5ee;
  background: #ffffff;
}

.admin-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 0 8px 14px;
  border-bottom: 1px solid #edf1f5;
  font-weight: 800;
}

.admin-menu {
  display: grid;
  gap: 4px;
  margin-top: 14px;
}

.admin-menu a {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  padding: 0 10px;
  border-radius: 6px;
  color: #475569;
  font-weight: 700;
}

.admin-menu a.router-link-active {
  color: #0f5132;
  background: #e8f2ec;
}

.admin-main {
  min-width: 0;
}

.admin-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 58px;
  padding: 0 22px;
  border-bottom: 1px solid #dfe5ee;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(12px);
}

.admin-header div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.admin-header span {
  color: #64748b;
  font-size: 13px;
}

.admin-page {
  padding: 22px;
}

.admin-page-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}

.admin-page-head h1 {
  margin: 0 0 4px;
  font-size: 24px;
}

.admin-page-head p {
  margin: 0;
  color: #64748b;
}

.admin-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.admin-metric,
.admin-panel {
  border: 1px solid #dfe5ee;
  border-radius: 8px;
  background: #ffffff;
}

.admin-metric {
  padding: 14px;
}

.admin-metric span {
  color: #64748b;
  font-size: 13px;
}

.admin-metric strong {
  display: block;
  margin-top: 8px;
  font-size: 24px;
}

.admin-grid.two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.admin-panel {
  padding: 14px;
}

.admin-panel h2 {
  margin-bottom: 12px;
  font-size: 16px;
}

@media (max-width: 900px) {
  .admin-console {
    grid-template-columns: 1fr;
  }

  .admin-sidebar {
    position: static;
    height: auto;
  }

  .admin-grid.two {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 12: Build and refine**

Run:

```powershell
cd frontend
npm run test:unit
npm run build
```

Expected: unit tests PASS and Vite build succeeds.

- [ ] **Step 13: Commit**

```powershell
git add frontend/src/views/admin frontend/src/styles/main.css
git commit -m "feat: add admin console views"
```

## Task 8: Final Integration Verification

**Files:**

- Read: `docs/superpowers/specs/2026-04-30-admin-console-design.md`
- Read: `docs/superpowers/plans/2026-04-30-admin-console.md`

- [ ] **Step 1: Run backend verification**

Run:

```powershell
cd backend
uv run pytest -q
uv run python manage.py check
```

Expected: all tests PASS and Django check reports no issues.

- [ ] **Step 2: Run frontend verification**

Run:

```powershell
cd frontend
npm run test:unit
npm run build
```

Expected: Vitest passes and Vite build completes.

- [ ] **Step 3: Start local services for manual verification**

Run backend:

```powershell
cd backend
uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000
```

Run frontend in another terminal:

```powershell
cd frontend
npm run dev
```

Expected: frontend URL is printed by Vite, commonly `http://localhost:5173`.

- [ ] **Step 4: Manual browser flow**

Verify these flows:

1. Log in as a staff user.
2. Open `/admin-console`.
3. Confirm dashboard metrics load.
4. Open products and inventory.
5. Preview and commit a card import with reason `Manual verification restock`.
6. Create a customer order from `/`.
7. Return to `/admin-console/orders`.
8. Mark the order paid with reason `Manual verification payment`.
9. Open logs and confirm `inventory.import` and `order.mark_paid` entries exist.

- [ ] **Step 5: Check git status**

Run:

```powershell
git status --short
```

Expected: only intended files are modified. Leave `docker-compose.yml` unstaged when it still appears as an unrelated working-tree change.

- [ ] **Step 6: Commit final verification note if code changed during fixes**

If verification required code changes, commit them:

```powershell
git add backend frontend
git commit -m "fix: polish admin console integration"
```

If verification required no code changes, do not create an empty commit.
