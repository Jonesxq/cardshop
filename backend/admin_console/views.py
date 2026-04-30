from django.db.models import Count, Q
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
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
