from urllib.parse import urlencode
import hashlib

from django.conf import settings


def sign_params(params, key=None):
    key = key if key is not None else settings.EASYPAY_KEY
    filtered = {
        k: v
        for k, v in params.items()
        if k not in {"sign", "sign_type"} and v is not None and str(v) != ""
    }
    query = "&".join(f"{k}={filtered[k]}" for k in sorted(filtered))
    return hashlib.md5(f"{query}{key}".encode("utf-8")).hexdigest()


def verify_notify(params):
    received = params.get("sign", "")
    return bool(received) and received == sign_params(params)


def build_payment_response(order, request):
    notify_url = request.build_absolute_uri("/api/payments/easypay/notify")
    return_url = f"{settings.SITE_URL}/orders?keyword={order.order_no}"
    base = {
        "pid": settings.EASYPAY_PID,
        "type": order.pay_type,
        "out_trade_no": order.order_no,
        "notify_url": notify_url,
        "return_url": return_url,
        "name": order.product.name,
        "money": str(order.amount),
        "sitename": "AI 发卡商城",
    }
    base["sign"] = sign_params(base)
    base["sign_type"] = "MD5"
    if not settings.EASYPAY_PID or not settings.EASYPAY_KEY or not settings.EASYPAY_GATEWAY_URL:
        return {
            "mode": "dev",
            "params": base,
            "dev_complete_url": request.build_absolute_uri("/api/payments/dev/complete"),
        }
    return {
        "mode": "easypay",
        "gateway_url": settings.EASYPAY_GATEWAY_URL,
        "method": "GET",
        "params": base,
        "redirect_url": f"{settings.EASYPAY_GATEWAY_URL}?{urlencode(base)}",
    }

