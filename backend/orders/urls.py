from django.urls import path

from .views import CreateOrderView, OrderPaymentView, QueryOrderView

urlpatterns = [
    path("", CreateOrderView.as_view()),
    path("query", QueryOrderView.as_view()),
    path("<str:order_no>/payment", OrderPaymentView.as_view()),
]
