import base64
import binascii
import json
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


ALIPAY_METHOD = "alipay.trade.page.pay"


def _as_text(value):
    if isinstance(value, (list, tuple)):
        return _as_text(value[0]) if value else ""
    if value is None:
        return ""
    return str(value)


def _wrap_pem(raw_key, marker):
    key = (raw_key or "").strip().replace("\\n", "\n")
    if not key:
        raise ImproperlyConfigured(f"缺少支付宝{marker}")
    if "BEGIN " in key:
        return key.encode("utf-8")
    compact = "".join(key.split())
    return f"-----BEGIN {marker}-----\n{compact}\n-----END {marker}-----\n".encode("utf-8")


def _load_private_key(raw_key=None):
    key = raw_key if raw_key is not None else settings.ALIPAY_APP_PRIVATE_KEY
    try:
        return serialization.load_pem_private_key(_wrap_pem(key, "PRIVATE KEY"), password=None)
    except ValueError:
        return serialization.load_pem_private_key(_wrap_pem(key, "RSA PRIVATE KEY"), password=None)


def _load_public_key(raw_key=None):
    key = raw_key if raw_key is not None else settings.ALIPAY_PUBLIC_KEY
    return serialization.load_pem_public_key(_wrap_pem(key, "PUBLIC KEY"))


def canonicalize(params, include_sign_type=True):
    filtered = {
        key: _as_text(value)
        for key, value in params.items()
        if key != "sign" and (include_sign_type or key != "sign_type") and _as_text(value) != ""
    }
    return "&".join(f"{key}={filtered[key]}" for key in sorted(filtered))


def sign_params(params, private_key=None):
    key = _load_private_key(private_key)
    signature = key.sign(
        canonicalize(params).encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def verify_params(params, public_key=None):
    signature = _as_text(params.get("sign"))
    if not signature:
        return False
    key = _load_public_key(public_key)
    try:
        decoded_signature = base64.b64decode(signature)
    except (ValueError, binascii.Error):
        return False
    for include_sign_type in (True, False):
        try:
            key.verify(
                decoded_signature,
                canonicalize(params, include_sign_type=include_sign_type).encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            continue
    return False


def ensure_alipay_configured():
    missing = []
    if not settings.ALIPAY_APP_ID:
        missing.append("ALIPAY_APP_ID")
    if not settings.ALIPAY_APP_PRIVATE_KEY:
        missing.append("ALIPAY_APP_PRIVATE_KEY")
    if not settings.ALIPAY_PUBLIC_KEY:
        missing.append("ALIPAY_PUBLIC_KEY")
    if missing:
        raise ImproperlyConfigured(f"支付宝配置缺失：{', '.join(missing)}")


def build_alipay_payment_response(order, request):
    ensure_alipay_configured()
    notify_url = settings.ALIPAY_NOTIFY_URL or request.build_absolute_uri("/api/payments/alipay/notify")
    return_url = settings.ALIPAY_RETURN_URL or f"{settings.SITE_URL}/orders?keyword={order.order_no}"
    biz_content = {
        "out_trade_no": order.order_no,
        "product_code": "FAST_INSTANT_TRADE_PAY",
        "total_amount": str(Decimal(order.amount).quantize(Decimal("0.01"))),
        "subject": order.product.name,
        "timeout_express": "15m",
    }
    params = {
        "app_id": settings.ALIPAY_APP_ID,
        "method": ALIPAY_METHOD,
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now(ZoneInfo(settings.TIME_ZONE)).strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": notify_url,
        "return_url": return_url,
        "biz_content": json.dumps(biz_content, ensure_ascii=False, separators=(",", ":")),
    }
    params["sign"] = sign_params(params)
    return {
        "mode": "alipay",
        "gateway_url": settings.ALIPAY_GATEWAY_URL,
        "method": "GET",
        "params": params,
        "redirect_url": f"{settings.ALIPAY_GATEWAY_URL}?{urlencode(params)}",
    }


def normalize_notify_payload(payload):
    return {key: _as_text(value) for key, value in payload.items()}
