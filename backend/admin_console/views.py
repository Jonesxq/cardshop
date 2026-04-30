from django.db.models import Q
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order, PaymentTransaction
from shop.models import CardSecret, Category, Product

from .dashboard import get_dashboard_payload
from .permissions import IsAdminConsoleUser, has_admin_permission
from .serializers import (
    CardAdminSerializer,
    CategorySerializer,
    OrderAdminSerializer,
    PaymentAdminSerializer,
    ProductSerializer,
    serialize_admin_me,
)


PERMISSION_ALIASES = {
    "can_manage_products": ("can_manage_inventory",),
    "can_view_dashboard": ("can_manage_inventory", "can_manage_orders", "can_manage_payments", "can_manage_staff"),
    "can_view_payments": ("can_manage_payments",),
    "can_view_sensitive_payload": ("can_manage_payments",),
}


def user_has_admin_permission(user, permission):
    return has_admin_permission(user, permission) or any(
        has_admin_permission(user, alias) for alias in PERMISSION_ALIASES.get(permission, ())
    )


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
        if self.required_permission and not user_has_admin_permission(request.user, self.required_permission):
            raise PermissionDenied()


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
        return Product.objects.select_related("category").prefetch_related("cards").order_by("sort_order", "id")


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


class CardListView(RequirePermissionMixin, generics.ListAPIView):
    serializer_class = CardAdminSerializer
    required_permission = "can_manage_inventory"

    def get_queryset(self):
        return CardSecret.objects.select_related("product", "reserved_order").order_by("-created_at", "id")


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
        context["can_view_sensitive_payload"] = user_has_admin_permission(
            self.request.user, "can_view_sensitive_payload"
        )
        return context


class PaymentDetailView(RequirePermissionMixin, generics.RetrieveAPIView):
    serializer_class = PaymentAdminSerializer
    required_permission = "can_view_payments"

    def get_queryset(self):
        return PaymentTransaction.objects.select_related("order")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["can_view_sensitive_payload"] = user_has_admin_permission(
            self.request.user, "can_view_sensitive_payload"
        )
        return context
