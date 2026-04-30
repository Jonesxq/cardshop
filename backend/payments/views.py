import logging

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from orders.serializers import OrderListSerializer
from orders.services import complete_order_payment, get_order_for_payment
from .alipay import normalize_notify_payload, verify_params as verify_alipay_notify
from .easypay import verify_notify


notify_logger = logging.getLogger("cardshop.payments.notify")
security_logger = logging.getLogger("cardshop.security")


class EasypayNotifyView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        payload = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
        if not verify_notify(payload):
            security_logger.warning(
                "event=payment_notify_invalid_signature outcome=rejected provider=easypay out_trade_no=%s "
                "trade_no=%s client_ip=%s",
                payload.get("out_trade_no", "") or "-",
                payload.get("trade_no", "") or "-",
                request.META.get("REMOTE_ADDR", "") or "-",
            )
            return Response({"detail": "invalid sign"}, status=status.HTTP_400_BAD_REQUEST)
        trade_status = payload.get("trade_status", "TRADE_SUCCESS")
        if trade_status not in {"TRADE_SUCCESS", "success", "SUCCESS"}:
            notify_logger.info(
                "event=payment_notify_ignored outcome=ignored provider=easypay out_trade_no=%s trade_status=%s",
                payload.get("out_trade_no", "") or "-",
                trade_status or "-",
            )
            return Response("success")
        try:
            complete_order_payment(
                order_no=payload.get("out_trade_no", ""),
                amount=payload.get("money", "0"),
                provider="easypay",
                trade_no=payload.get("trade_no", ""),
                raw_payload=payload,
            )
        except (Order.DoesNotExist, DjangoValidationError) as exc:
            notify_logger.warning(
                "event=payment_notify_failed outcome=failed provider=easypay out_trade_no=%s reason=%s",
                payload.get("out_trade_no", "") or "-",
                exc.__class__.__name__,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response("success")


class AlipayNotifyView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        payload = normalize_notify_payload(request.data.dict() if hasattr(request.data, "dict") else dict(request.data))
        if not verify_alipay_notify(payload):
            security_logger.warning(
                "event=payment_notify_invalid_signature outcome=rejected provider=alipay out_trade_no=%s trade_no=%s "
                "client_ip=%s",
                payload.get("out_trade_no", "") or "-",
                payload.get("trade_no", "") or "-",
                request.META.get("REMOTE_ADDR", "") or "-",
            )
            return HttpResponse("failure", status=400)
        if payload.get("app_id") != settings.ALIPAY_APP_ID:
            security_logger.warning(
                "event=payment_notify_app_mismatch outcome=rejected provider=alipay out_trade_no=%s app_id=%s",
                payload.get("out_trade_no", "") or "-",
                payload.get("app_id", "") or "-",
            )
            return HttpResponse("failure", status=400)
        trade_status = payload.get("trade_status")
        if trade_status not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
            notify_logger.info(
                "event=payment_notify_ignored outcome=ignored provider=alipay out_trade_no=%s trade_status=%s",
                payload.get("out_trade_no", "") or "-",
                trade_status or "-",
            )
            return HttpResponse("success")
        try:
            complete_order_payment(
                order_no=payload.get("out_trade_no", ""),
                amount=payload.get("total_amount", "0"),
                provider="alipay",
                trade_no=payload.get("trade_no", ""),
                raw_payload=payload,
            )
        except (Order.DoesNotExist, DjangoValidationError):
            notify_logger.warning(
                "event=payment_notify_failed outcome=failed provider=alipay out_trade_no=%s",
                payload.get("out_trade_no", "") or "-",
            )
            return HttpResponse("failure", status=400)
        return HttpResponse("success")


class DevCompletePaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not settings.DEBUG:
            return Response({"detail": "dev payment is disabled"}, status=status.HTTP_403_FORBIDDEN)
        try:
            order = get_order_for_payment(
                order_no=request.data.get("order_no"),
                contact=request.data.get("contact", ""),
                user=request.user,
            )
            order = complete_order_payment(
                order_no=order.order_no,
                amount=order.amount,
                provider="dev",
                trade_no=f"DEV-{order.order_no}",
                raw_payload={"source": "dev_complete"},
            )
        except (Order.DoesNotExist, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderListSerializer(order).data)
