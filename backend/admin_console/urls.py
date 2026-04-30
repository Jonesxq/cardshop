from django.urls import path

from .views import (
    AdminDashboardView,
    AdminMeView,
    CardListView,
    CategoryDetailView,
    CategoryListCreateView,
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
