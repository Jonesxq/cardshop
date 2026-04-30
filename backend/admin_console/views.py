from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order, PaymentTransaction
from shop.models import Announcement, CardSecret, Category, Product, SiteConfig
from shop.services import DEFAULT_SITE

from .audit import record_operation
from .dashboard import get_dashboard_payload
from .inventory import (
    MAX_IMPORT_CHARS,
    MAX_IMPORT_ROWS,
    build_import_preview,
    commit_card_import,
    without_valid_values,
)
from .order_actions import (
    admin_cancel_order,
    admin_mark_paid,
    admin_redeliver_order,
    admin_release_stock,
    admin_replace_card,
    resolve_payment_exception,
)
from .models import AdminOperationLog, AdminProfile
from .permissions import IsAdminConsoleUser, get_admin_role, has_admin_permission
from .serializers import (
    AdminOperationLogSerializer,
    AnnouncementAdminSerializer,
    CardAdminSerializer,
    CategorySerializer,
    OrderAdminSerializer,
    PaymentAdminSerializer,
    ProductSerializer,
    SiteConfigAdminSerializer,
    SiteConfigUpdateSerializer,
    UserAdminSerializer,
    UserAdminUpdateSerializer,
    serialize_admin_me,
)


ALLOWED_SITE_CONFIG_KEYS = set(DEFAULT_SITE)


def get_stock_counts_by_product(product_ids):
    stock_map = {
        product_id: {"available": 0, "reserved": 0, "sold": 0, "void": 0}
        for product_id in product_ids
    }
    rows = (
        CardSecret.objects.filter(product_id__in=product_ids)
        .values("product_id", "status")
        .annotate(count=Count("id"))
    )
    for row in rows:
        stock_map[row["product_id"]][row["status"]] = row["count"]
    return stock_map


class AdminPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class RequirePermissionMixin:
    permission_classes = [IsAdminConsoleUser]
    pagination_class = AdminPagination
    required_permission = ""

    def check_permissions(self, request):
        super().check_permissions(request)
        if self.required_permission and not has_admin_permission(request.user, self.required_permission):
            raise PermissionDenied()


class CardImportRequestSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    cards = serializers.CharField(allow_blank=True, trim_whitespace=False)
    reason = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    def validate_cards(self, value):
        if len(value) > MAX_IMPORT_CHARS:
            raise serializers.ValidationError(f"Ensure this field has no more than {MAX_IMPORT_CHARS} characters.")
        if len(value.splitlines()) > MAX_IMPORT_ROWS:
            raise serializers.ValidationError(f"Ensure this import has no more than {MAX_IMPORT_ROWS} rows.")
        return value


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)


class AdminMeView(APIView):
    permission_classes = [IsAdminConsoleUser]

    def get(self, request):
        return Response(serialize_admin_me(request.user))


class AdminDashboardView(RequirePermissionMixin, APIView):
    required_permission = "can_view_dashboard"

    def get(self, request):
        return Response(get_dashboard_payload())


class ProductListCreateView(RequirePermissionMixin, generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    required_permission = "can_manage_products"

    def get_queryset(self):
        queryset = Product.objects.select_related("category").order_by("sort_order", "id")
        keyword = self.request.query_params.get("keyword")
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            context = self.get_serializer_context()
            context["stock_counts_by_product"] = get_stock_counts_by_product([product.id for product in page])
            serializer = self.get_serializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)

        products = list(queryset)
        context = self.get_serializer_context()
        context["stock_counts_by_product"] = get_stock_counts_by_product([product.id for product in products])
        serializer = self.get_serializer(products, many=True, context=context)
        return Response(serializer.data)


class ProductDetailView(RequirePermissionMixin, generics.RetrieveUpdateAPIView):
    serializer_class = ProductSerializer
    required_permission = "can_manage_products"
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("cards")


class CategoryListCreateView(RequirePermissionMixin, generics.ListCreateAPIView):
    serializer_class = CategorySerializer
    required_permission = "can_manage_products"
    queryset = Category.objects.all().order_by("sort_order", "id")


class CategoryDetailView(RequirePermissionMixin, generics.RetrieveUpdateAPIView):
    serializer_class = CategorySerializer
    required_permission = "can_manage_products"
    http_method_names = ["get", "patch", "head", "options"]
    queryset = Category.objects.all()


class AnnouncementListCreateView(RequirePermissionMixin, generics.ListCreateAPIView):
    serializer_class = AnnouncementAdminSerializer
    required_permission = "can_manage_products"
    queryset = Announcement.objects.all().order_by("sort_order", "-created_at", "-id")


class AnnouncementDetailView(RequirePermissionMixin, generics.RetrieveUpdateAPIView):
    serializer_class = AnnouncementAdminSerializer
    required_permission = "can_manage_products"
    http_method_names = ["get", "patch", "head", "options"]
    queryset = Announcement.objects.all()


class UserListView(RequirePermissionMixin, generics.ListAPIView):
    serializer_class = UserAdminSerializer
    required_permission = "can_manage_users"

    def get_queryset(self):
        queryset = (
            get_user_model()
            .objects.select_related("admin_profile")
            .annotate(
                order_count=Count("order", distinct=True),
                total_paid_amount=Coalesce(
                    Sum("order__amount", filter=Q(order__status=Order.Status.PAID)),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
            )
            .order_by("id")
        )
        keyword = self.request.query_params.get("keyword")
        if keyword:
            queryset = queryset.filter(Q(email__icontains=keyword) | Q(username__icontains=keyword))
        return queryset


def _staff_snapshot(user):
    return {
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "role": get_admin_role(user),
    }


def _has_active_staff_superadmin_excluding(user, *, lock=False):
    queryset = (
        get_user_model()
        .objects.exclude(id=user.id)
        .filter(is_active=True, is_staff=True)
        .filter(Q(is_superuser=True) | Q(admin_profile__role=AdminProfile.Role.SUPERADMIN))
    )
    if lock:
        queryset = queryset.select_for_update()
    return queryset.exists()


def _validate_staff_update(request, user, data, before):
    next_is_active = data.get("is_active", user.is_active)
    next_is_staff = data.get("is_staff", user.is_staff)
    next_role = data.get("role", before["role"])

    if request.user.id == user.id:
        if user.is_active and next_is_active is False:
            raise ValidationError({"is_active": "You cannot disable your own admin account."})
        if user.is_staff and next_is_staff is False:
            raise ValidationError({"is_staff": "You cannot remove your own staff access."})
        if before["role"] == AdminProfile.Role.SUPERADMIN and next_role != AdminProfile.Role.SUPERADMIN:
            raise ValidationError({"role": "You cannot demote your own superadmin role."})

    target_remains_superadmin = bool(
        next_is_active
        and next_is_staff
        and (user.is_superuser or next_role == AdminProfile.Role.SUPERADMIN)
    )
    if not target_remains_superadmin and not _has_active_staff_superadmin_excluding(user, lock=True):
        raise ValidationError({"role": "At least one active staff superadmin is required."})


class UserDetailView(RequirePermissionMixin, generics.RetrieveUpdateAPIView):
    serializer_class = UserAdminSerializer
    required_permission = "can_manage_staff"
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return get_user_model().objects.select_related("admin_profile")

    def patch(self, request, *args, **kwargs):
        serializer = UserAdminUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            queryset = self.filter_queryset(self.get_queryset().select_for_update())
            user = get_object_or_404(queryset, pk=kwargs["pk"])
            before = _staff_snapshot(user)
            _validate_staff_update(request, user, serializer.validated_data, before)

            for field in ("is_active", "is_staff"):
                if field in serializer.validated_data:
                    setattr(user, field, serializer.validated_data[field])
            user.save(update_fields=["is_active", "is_staff"])

            role = serializer.validated_data.get("role")
            if role is not None:
                AdminProfile.objects.update_or_create(user=user, defaults={"role": role})
            user.refresh_from_db()
            after = _staff_snapshot(user)
            record_operation(
                request=request,
                action="user.update_staff",
                target=user,
                reason=serializer.validated_data["reason"],
                before=before,
                after=after,
            )

        return Response(UserAdminSerializer(user).data)


class CardListView(RequirePermissionMixin, generics.ListAPIView):
    serializer_class = CardAdminSerializer
    required_permission = "can_manage_inventory"

    def get_queryset(self):
        queryset = CardSecret.objects.select_related("product", "reserved_order").order_by("-created_at", "id")
        product_id = self.request.query_params.get("product_id")
        if product_id:
            if not product_id.isdecimal():
                raise ValidationError({"product_id": "Enter a valid integer."})
            queryset = queryset.filter(product_id=product_id)
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class CardImportPreviewView(RequirePermissionMixin, APIView):
    required_permission = "can_manage_inventory"

    def post(self, request):
        serializer = CardImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, id=serializer.validated_data["product_id"])
        preview = build_import_preview(product, serializer.validated_data["cards"])
        return Response(without_valid_values(preview))


class CardImportCommitView(RequirePermissionMixin, APIView):
    required_permission = "can_manage_inventory"

    def post(self, request):
        serializer = CardImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "").strip()
        if not reason:
            raise ValidationError({"reason": "This field may not be blank."})

        _, result = commit_card_import(
            product_id=serializer.validated_data["product_id"],
            cards=serializer.validated_data["cards"],
            request=request,
            reason=reason,
        )
        return Response(result)


class OrderListView(RequirePermissionMixin, generics.ListAPIView):
    serializer_class = OrderAdminSerializer
    required_permission = "can_manage_orders"

    def get_queryset(self):
        queryset = Order.objects.select_related("user", "product").order_by("-created_at", "-id")
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        keyword = self.request.query_params.get("keyword")
        if keyword:
            queryset = queryset.filter(Q(order_no__icontains=keyword) | Q(contact__icontains=keyword))
        return queryset


class OrderDetailView(RequirePermissionMixin, generics.RetrieveAPIView):
    serializer_class = OrderAdminSerializer
    required_permission = "can_manage_orders"

    def get_queryset(self):
        return Order.objects.select_related("user", "product")


def _as_drf_validation_error(error):
    if hasattr(error, "message_dict"):
        return error.message_dict
    if hasattr(error, "messages"):
        return error.messages
    return str(error)


class OrderActionView(RequirePermissionMixin, APIView):
    required_permission = "can_manage_orders"
    action = ""
    service = None

    def post(self, request, order_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        try:
            with transaction.atomic():
                order, before, after = self.service(order_id)
                log = record_operation(
                    request=request,
                    action=self.action,
                    target=order,
                    reason=reason,
                    before=before,
                    after=after,
                )
        except ObjectDoesNotExist:
            raise Http404
        except DjangoValidationError as exc:
            raise ValidationError(_as_drf_validation_error(exc))

        data = dict(OrderAdminSerializer(order).data)
        data["log_id"] = log.id
        return Response(data)


class MarkPaidView(OrderActionView):
    action = "order.mark_paid"
    service = staticmethod(admin_mark_paid)


class CancelOrderView(OrderActionView):
    action = "order.cancel"
    service = staticmethod(admin_cancel_order)


class RedeliverOrderView(OrderActionView):
    action = "order.redeliver"
    service = staticmethod(admin_redeliver_order)


class ReplaceCardView(OrderActionView):
    action = "order.replace_card"
    service = staticmethod(admin_replace_card)


class ReleaseStockView(OrderActionView):
    action = "order.release_stock"
    service = staticmethod(admin_release_stock)


class PaymentListView(RequirePermissionMixin, generics.ListAPIView):
    serializer_class = PaymentAdminSerializer
    required_permission = "can_view_payments"

    def get_queryset(self):
        queryset = PaymentTransaction.objects.select_related("order").order_by("-created_at", "-id")
        provider = self.request.query_params.get("provider")
        if provider:
            queryset = queryset.filter(provider=provider)
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["can_view_sensitive_payload"] = has_admin_permission(self.request.user, "can_view_sensitive_payload")
        return context


class PaymentDetailView(RequirePermissionMixin, generics.RetrieveAPIView):
    serializer_class = PaymentAdminSerializer
    required_permission = "can_view_payments"

    def get_queryset(self):
        return PaymentTransaction.objects.select_related("order")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["can_view_sensitive_payload"] = has_admin_permission(self.request.user, "can_view_sensitive_payload")
        return context


class PaymentResolveView(RequirePermissionMixin, APIView):
    required_permission = "can_resolve_payments"

    def post(self, request, payment_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        if len(reason) > PaymentTransaction._meta.get_field("note").max_length:
            raise ValidationError({"reason": "Ensure this field has no more than 255 characters."})
        try:
            with transaction.atomic():
                payment, before, after = resolve_payment_exception(payment_id, reason)
                log = record_operation(
                    request=request,
                    action="payment.resolve",
                    target=payment,
                    reason=reason,
                    before=before,
                    after=after,
                )
        except ObjectDoesNotExist:
            raise Http404
        except DjangoValidationError as exc:
            raise ValidationError(_as_drf_validation_error(exc))

        context = {"can_view_sensitive_payload": has_admin_permission(request.user, "can_view_sensitive_payload")}
        data = dict(PaymentAdminSerializer(payment, context=context).data)
        data["log_id"] = log.id
        return Response(data)


class SiteConfigListView(RequirePermissionMixin, generics.ListAPIView):
    serializer_class = SiteConfigAdminSerializer
    required_permission = "can_manage_settings"
    queryset = SiteConfig.objects.all().order_by("key")


class SiteConfigDetailView(RequirePermissionMixin, APIView):
    required_permission = "can_manage_settings"

    def patch(self, request, key):
        if key not in ALLOWED_SITE_CONFIG_KEYS:
            raise ValidationError({"key": "Unsupported site config key."})
        serializer = SiteConfigUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            config, _created = SiteConfig.objects.get_or_create(key=key)
            before = {
                "key": config.key,
                "label": config.label,
                "value": config.value,
            }
            for field in ("label", "value"):
                if field in serializer.validated_data:
                    setattr(config, field, serializer.validated_data[field])
            config.save()
            after = {
                "key": config.key,
                "label": config.label,
                "value": config.value,
            }
            record_operation(
                request=request,
                action="site_config.update",
                target=config,
                before=before,
                after=after,
            )

        return Response(SiteConfigAdminSerializer(config).data)


class OperationLogListView(RequirePermissionMixin, generics.ListAPIView):
    serializer_class = AdminOperationLogSerializer
    required_permission = "can_view_logs"
    queryset = AdminOperationLog.objects.all()
