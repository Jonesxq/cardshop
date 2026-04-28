from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import EmailCodeView, LoginView, MeView, MyOrdersView, RegisterView, ResetPasswordView

urlpatterns = [
    path("email-code", EmailCodeView.as_view()),
    path("register", RegisterView.as_view()),
    path("login", LoginView.as_view()),
    path("token/refresh", TokenRefreshView.as_view()),
    path("reset-password", ResetPasswordView.as_view()),
    path("me", MeView.as_view()),
    path("orders", MyOrdersView.as_view()),
]
