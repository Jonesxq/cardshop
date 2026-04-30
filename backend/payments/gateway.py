import logging

from django.conf import settings

from .alipay import build_alipay_payment_response
from .easypay import build_payment_response as build_easypay_payment_response


payments_logger = logging.getLogger("cardshop.payments")


def build_dev_payment_response(order, request):
    return {
        "mode": "dev",
        "params": {
            "out_trade_no": order.order_no,
            "money": str(order.amount),
            "type": order.pay_type,
            "name": order.product.name,
        },
        "dev_complete_url": request.build_absolute_uri("/api/payments/dev/complete"),
    }


def build_payment_response(order, request):
    provider = settings.PAYMENT_PROVIDER
    if provider == "alipay":
        response = build_alipay_payment_response(order, request)
    elif provider == "easypay":
        response = build_easypay_payment_response(order, request)
    else:
        response = build_dev_payment_response(order, request)
    payments_logger.info(
        "event=payment_response_built outcome=success order_no=%s provider=%s amount=%s mode=%s",
        order.order_no,
        provider,
        order.amount,
        response.get("mode", "-"),
    )
    return response
