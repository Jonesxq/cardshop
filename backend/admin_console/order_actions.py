from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from orders.models import Order, PaymentTransaction
from orders.services import complete_order_payment
from shop.models import CardSecret


def _isoformat(value):
    return value.isoformat() if value else None


def order_snapshot(order):
    return {
        "id": order.id,
        "order_no": order.order_no,
        "status": order.status,
        "quantity": order.quantity,
        "amount": str(order.amount),
        "paid_at": _isoformat(order.paid_at),
        "delivered_at": _isoformat(order.delivered_at),
        "delivery_items": list(order.delivery_items or []),
        "reserved_card_ids": list(order.reserved_cards.order_by("id").values_list("id", flat=True)),
    }


def payment_snapshot(payment):
    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "provider": payment.provider,
        "trade_no": payment.trade_no,
        "out_trade_no": payment.out_trade_no,
        "amount": str(payment.amount),
        "status": payment.status,
        "note": payment.note,
    }


def _release_reserved_cards(order):
    CardSecret.objects.filter(reserved_order=order, status=CardSecret.Status.RESERVED).update(
        status=CardSecret.Status.AVAILABLE,
        reserved_order=None,
        reserved_until=None,
    )


def admin_mark_paid(order_id):
    order = Order.objects.select_related("product").prefetch_related("reserved_cards").get(id=order_id)
    before = order_snapshot(order)
    order = complete_order_payment(
        order_no=order.order_no,
        amount=order.amount,
        provider="admin_console",
        raw_payload={},
    )
    order.refresh_from_db()
    after = order_snapshot(order)
    return order, before, after


def admin_cancel_order(order_id):
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("product").get(id=order_id)
        before = order_snapshot(order)
        if order.status == Order.Status.PAID:
            raise ValidationError("Paid orders cannot be cancelled.")
        if order.status not in {Order.Status.PENDING, Order.Status.EXPIRED}:
            raise ValidationError("Order cannot be cancelled from its current status.")
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        _release_reserved_cards(order)
        order.refresh_from_db()
        after = order_snapshot(order)
    return order, before, after


def admin_release_stock(order_id):
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("product").get(id=order_id)
        before = order_snapshot(order)
        if order.status != Order.Status.PENDING:
            raise ValidationError("Only pending orders can release stock.")
        order.status = Order.Status.EXPIRED
        order.save(update_fields=["status", "updated_at"])
        _release_reserved_cards(order)
        order.refresh_from_db()
        after = order_snapshot(order)
    return order, before, after


def admin_redeliver_order(order_id):
    order = Order.objects.select_related("product").prefetch_related("reserved_cards").get(id=order_id)
    before = order_snapshot(order)
    if order.status != Order.Status.PAID:
        raise ValidationError("Only paid orders can be redelivered.")
    after = order_snapshot(order)
    return order, before, after


def admin_replace_card(order_id):
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("product").get(id=order_id)
        before = order_snapshot(order)
        if order.status != Order.Status.PAID:
            raise ValidationError("Only paid orders can have cards replaced.")

        old_cards = list(
            CardSecret.objects.select_for_update().filter(
                reserved_order=order,
                status=CardSecret.Status.SOLD,
            )
        )
        new_cards = list(
            CardSecret.objects.select_for_update()
            .filter(product=order.product, status=CardSecret.Status.AVAILABLE)
            .order_by("id")[: order.quantity]
        )
        if len(new_cards) < order.quantity:
            raise ValidationError("Insufficient available cards for replacement.")

        now = timezone.now()
        for card in old_cards:
            card.status = CardSecret.Status.VOID
        CardSecret.objects.bulk_update(old_cards, ["status"])

        delivered = []
        for card in new_cards:
            delivered.append(card.get_secret())
            card.status = CardSecret.Status.SOLD
            card.reserved_order = order
            card.reserved_until = None
            card.sold_at = now
        CardSecret.objects.bulk_update(new_cards, ["status", "reserved_order", "reserved_until", "sold_at"])

        order.delivery_items = delivered
        order.delivered_at = now
        order.save(update_fields=["delivery_items", "delivered_at", "updated_at"])
        order.refresh_from_db()
        after = order_snapshot(order)
    return order, before, after


def resolve_payment_exception(payment_id, reason):
    with transaction.atomic():
        payment = PaymentTransaction.objects.select_for_update().select_related("order").get(id=payment_id)
        before = payment_snapshot(payment)
        if payment.status == PaymentTransaction.Status.SUCCESS:
            raise ValidationError("Successful payments cannot be resolved as exceptions.")
        payment.status = PaymentTransaction.Status.IGNORED
        payment.note = reason
        payment.save(update_fields=["status", "note"])
        payment.refresh_from_db()
        after = payment_snapshot(payment)
    return payment, before, after
