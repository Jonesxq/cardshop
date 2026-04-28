from decimal import Decimal
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from shop.models import CardSecret, Product
from .models import Order, PaymentTransaction


class DuplicatePendingOrder(Exception):
    def __init__(self, order):
        self.order = order
        super().__init__("你已有该商品未支付订单，请先继续支付或等待订单过期")


def normalize_contact(value):
    return (value or "").strip().lower()


def generate_order_no():
    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"O{stamp}{secrets.token_hex(4).upper()}"


def expire_pending_orders(now=None):
    now = now or timezone.now()
    expired = list(
        Order.objects.filter(status=Order.Status.PENDING, expires_at__lt=now).values_list("id", flat=True)
    )
    if not expired:
        return 0
    with transaction.atomic():
        orders = Order.objects.select_for_update().filter(id__in=expired, status=Order.Status.PENDING)
        count = orders.update(status=Order.Status.EXPIRED)
        CardSecret.objects.filter(reserved_order_id__in=expired, status=CardSecret.Status.RESERVED).update(
            status=CardSecret.Status.AVAILABLE,
            reserved_order=None,
            reserved_until=None,
        )
    return count


def create_order(*, product_id, quantity, contact, pay_type="alipay", user=None):
    if quantity < 1:
        raise ValidationError("购买数量必须大于 0")
    contact = normalize_contact(contact)
    if not contact:
        raise ValidationError("请填写联系方式")
    expire_pending_orders()
    with transaction.atomic():
        product = Product.objects.select_for_update().get(id=product_id, is_active=True, category__is_active=True)
        if getattr(user, "is_authenticated", False):
            existing_order = (
                Order.objects.select_for_update()
                .filter(
                    user=user,
                    product=product,
                    status=Order.Status.PENDING,
                    expires_at__gt=timezone.now(),
                )
                .order_by("-created_at")
                .first()
            )
        else:
            existing_order = (
                Order.objects.select_for_update()
                .filter(
                    user__isnull=True,
                    contact__iexact=contact,
                    product=product,
                    status=Order.Status.PENDING,
                    expires_at__gt=timezone.now(),
                )
                .order_by("-created_at")
                .first()
            )
        if existing_order:
            raise DuplicatePendingOrder(existing_order)

        cards = list(
            CardSecret.objects.select_for_update()
            .filter(product=product, status=CardSecret.Status.AVAILABLE)
            .order_by("id")[:quantity]
        )
        if len(cards) < quantity:
            raise ValidationError("库存不足")
        expires_at = timezone.now() + timezone.timedelta(minutes=settings.ORDER_RESERVE_MINUTES)
        order = Order.objects.create(
            order_no=generate_order_no(),
            user=user if getattr(user, "is_authenticated", False) else None,
            product=product,
            quantity=quantity,
            contact=contact,
            amount=product.price * Decimal(quantity),
            pay_type=pay_type,
            expires_at=expires_at,
        )
        for card in cards:
            card.status = CardSecret.Status.RESERVED
            card.reserved_order = order
            card.reserved_until = expires_at
        CardSecret.objects.bulk_update(cards, ["status", "reserved_order", "reserved_until"])
    return order


def complete_order_payment(*, order_no, amount, provider="easypay", trade_no="", raw_payload=None):
    raw_payload = raw_payload or {}
    error_message = None
    result_order = None
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("product").get(order_no=order_no)
        amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        if order.amount != amount:
            PaymentTransaction.objects.create(
                order=order,
                provider=provider,
                trade_no=trade_no,
                out_trade_no=order_no,
                amount=amount,
                status=PaymentTransaction.Status.FAILED,
                raw_payload=raw_payload,
                note="支付金额与订单金额不一致",
            )
            error_message = "支付金额与订单金额不一致"
        elif order.status == Order.Status.PAID:
            PaymentTransaction.objects.create(
                order=order,
                provider=provider,
                trade_no=trade_no,
                out_trade_no=order_no,
                amount=amount,
                status=PaymentTransaction.Status.IGNORED,
                raw_payload=raw_payload,
                note="重复回调，订单已支付",
            )
            result_order = order
        elif order.status != Order.Status.PENDING:
            PaymentTransaction.objects.create(
                order=order,
                provider=provider,
                trade_no=trade_no,
                out_trade_no=order_no,
                amount=amount,
                status=PaymentTransaction.Status.FAILED,
                raw_payload=raw_payload,
                note=f"订单状态不可支付: {order.status}",
            )
            error_message = "订单当前状态不可支付"
        elif order.expires_at < timezone.now():
            order.status = Order.Status.EXPIRED
            order.save(update_fields=["status", "updated_at"])
            CardSecret.objects.filter(reserved_order=order, status=CardSecret.Status.RESERVED).update(
                status=CardSecret.Status.AVAILABLE,
                reserved_order=None,
                reserved_until=None,
            )
            PaymentTransaction.objects.create(
                order=order,
                provider=provider,
                trade_no=trade_no,
                out_trade_no=order_no,
                amount=amount,
                status=PaymentTransaction.Status.FAILED,
                raw_payload=raw_payload,
                note="订单已过期",
            )
            error_message = "订单已过期"
        else:
            cards = list(
                CardSecret.objects.select_for_update().filter(
                    reserved_order=order,
                    status=CardSecret.Status.RESERVED,
                )
            )
            if len(cards) != order.quantity:
                error_message = "预留库存异常，请联系售后"
            else:
                delivered = []
                for card in cards:
                    delivered.append(card.get_secret())
                    card.mark_sold()
                CardSecret.objects.bulk_update(cards, ["status", "sold_at", "reserved_until"])

                now = timezone.now()
                order.status = Order.Status.PAID
                order.paid_at = now
                order.delivered_at = now
                order.delivery_items = delivered
                order.save(update_fields=["status", "paid_at", "delivered_at", "delivery_items", "updated_at"])

                PaymentTransaction.objects.create(
                    order=order,
                    provider=provider,
                    trade_no=trade_no,
                    out_trade_no=order_no,
                    amount=amount,
                    status=PaymentTransaction.Status.SUCCESS,
                    raw_payload=raw_payload,
                )
                result_order = order
    if error_message:
        raise ValidationError(error_message)
    return result_order


def query_orders(keyword, *, user=None):
    expire_pending_orders()
    keyword = (keyword or "").strip()
    if not keyword:
        return Order.objects.none()
    queryset = Order.objects.filter(models_query(keyword))
    if user is not None:
        queryset = queryset.filter(user=user)
    return queryset.select_related("product").order_by("-created_at")[:20]


def query_order_by_credentials(*, order_no, contact, user=None):
    expire_pending_orders()
    order_no = (order_no or "").strip()
    contact = normalize_contact(contact)
    if not order_no or not contact:
        return Order.objects.none()
    queryset = Order.objects.filter(order_no=order_no, contact__iexact=contact)
    if getattr(user, "is_authenticated", False):
        queryset = queryset.filter(models_query_for_user_or_guest(user))
    else:
        queryset = queryset.filter(user__isnull=True)
    return queryset.select_related("product").order_by("-created_at")[:1]


def get_order_for_payment(*, order_no, contact="", user=None):
    expire_pending_orders()
    order_no = (order_no or "").strip()
    contact = normalize_contact(contact)
    queryset = Order.objects.select_related("product").filter(order_no=order_no)
    if getattr(user, "is_authenticated", False) and not contact:
        queryset = queryset.filter(user=user)
    elif getattr(user, "is_authenticated", False):
        queryset = queryset.filter(models_query_for_user_or_guest(user), contact__iexact=contact)
    else:
        queryset = queryset.filter(user__isnull=True, contact__iexact=contact)
    return queryset.get()


def models_query_for_user_or_guest(user):
    from django.db.models import Q

    return Q(user=user) | Q(user__isnull=True)


def models_query(keyword):
    from django.db.models import Q

    return Q(order_no=keyword) | Q(contact=keyword)
