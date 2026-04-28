from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.gateway import build_payment_response
from .models import Order
from .serializers import CreateOrderSerializer, OrderListSerializer
from .services import get_order_for_payment, query_order_by_credentials, query_orders


class CreateOrderView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(serializer.to_representation(order), status=status.HTTP_201_CREATED)


class QueryOrderView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        order_no = request.query_params.get("order_no", "")
        contact = request.query_params.get("contact", "")
        keyword = request.query_params.get("keyword", "")
        if order_no or contact or not request.user.is_authenticated:
            if not order_no or not contact:
                return Response({"detail": "请输入订单号和联系方式"}, status=status.HTTP_400_BAD_REQUEST)
            orders = query_order_by_credentials(order_no=order_no, contact=contact, user=request.user)
        else:
            orders = query_orders(keyword, user=request.user)
        return Response({"results": OrderListSerializer(orders, many=True).data})


class OrderPaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, order_no):
        try:
            order = get_order_for_payment(
                order_no=order_no,
                contact=request.data.get("contact", ""),
                user=request.user,
            )
        except Order.DoesNotExist:
            return Response({"detail": "订单不存在或联系方式不匹配"}, status=status.HTTP_404_NOT_FOUND)
        if order.status != Order.Status.PENDING:
            return Response({"detail": "订单当前状态不可支付"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payment = build_payment_response(order, request)
        except ImproperlyConfigured as exc:
            return Response({"payment": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "order_no": order.order_no,
                "amount": str(order.amount),
                "expires_at": order.expires_at.isoformat(),
                "payment": payment,
            }
        )
