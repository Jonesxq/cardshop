from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from orders.views import CreateOrderView, OrderPaymentView, QueryOrderView


@api_view(["GET"])
@permission_classes([AllowAny])
def health(_request):
    return Response({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/auth/", include("accounts.urls")),
    path("api/shop/", include("shop.urls")),
    path("api/orders", CreateOrderView.as_view()),
    path("api/orders/query", QueryOrderView.as_view()),
    path("api/orders/<str:order_no>/payment", OrderPaymentView.as_view()),
    path("api/payments/", include("payments.urls")),
    path("api/admin-console/", include("admin_console.urls")),
]
