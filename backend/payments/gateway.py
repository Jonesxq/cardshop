from django.conf import settings

from .alipay import build_alipay_payment_response
from .easypay import build_payment_response as build_easypay_payment_response


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
        return build_alipay_payment_response(order, request)
    if provider == "easypay":
        return build_easypay_payment_response(order, request)
    return build_dev_payment_response(order, request)
