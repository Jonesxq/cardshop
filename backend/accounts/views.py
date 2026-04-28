from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.serializers import OrderListSerializer
from orders.models import Order
from orders.services import expire_pending_orders
from .serializers import (
    EmailCodeSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
)


class EmailCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=201)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"id": request.user.id, "email": request.user.email})


class MyOrdersView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderListSerializer

    def get_queryset(self):
        expire_pending_orders()
        return Order.objects.filter(user=self.request.user).select_related("product").order_by("-created_at")
