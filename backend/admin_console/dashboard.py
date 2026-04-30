from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from orders.models import Order, PaymentTransaction
from shop.models import CardSecret, Product


def _money(value):
    return f"{value or Decimal('0.00'):.2f}"


def get_dashboard_payload():
    today = timezone.localdate()
    start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    end = start + timezone.timedelta(days=1)

    paid_today = Order.objects.filter(status=Order.Status.PAID, paid_at__gte=start, paid_at__lt=end)
    summary = paid_today.aggregate(
        today_order_count=Count("id"),
        today_paid_amount=Coalesce(Sum("amount"), Decimal("0.00")),
    )

    products = Product.objects.annotate(
        available_card_count=Count("cards", filter=Q(cards__status=CardSecret.Status.AVAILABLE)),
        paid_order_count=Count("orders", filter=Q(orders__status=Order.Status.PAID)),
        paid_order_amount=Coalesce(Sum("orders__amount", filter=Q(orders__status=Order.Status.PAID)), Decimal("0.00")),
    )

    low_stock_products = [
        {
            "id": product.id,
            "name": product.name,
            "available": product.available_card_count,
        }
        for product in products.filter(is_active=True, available_card_count__lte=5).order_by(
            "available_card_count", "id"
        )[:10]
    ]

    abnormal_payments = [
        {
            "id": payment.id,
            "order_no": payment.order.order_no,
            "provider": payment.provider,
            "status": payment.status,
            "amount": _money(payment.amount),
            "created_at": payment.created_at,
        }
        for payment in PaymentTransaction.objects.exclude(status=PaymentTransaction.Status.SUCCESS)
        .select_related("order")
        .order_by("-created_at")[:10]
    ]

    trend_start = today - timezone.timedelta(days=6)
    rows = {
        row["day"]: row
        for row in Order.objects.filter(status=Order.Status.PAID, paid_at__date__gte=trend_start)
        .annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(order_count=Count("id"), paid_amount=Coalesce(Sum("amount"), Decimal("0.00")))
    }
    trend = []
    for offset in range(7):
        day = trend_start + timezone.timedelta(days=offset)
        row = rows.get(day, {})
        trend.append(
            {
                "date": day.isoformat(),
                "order_count": row.get("order_count", 0),
                "paid_amount": _money(row.get("paid_amount")),
            }
        )

    top_products = [
        {
            "id": product.id,
            "name": product.name,
            "paid_order_count": product.paid_order_count,
            "paid_amount": _money(product.paid_order_amount),
        }
        for product in products.order_by("-paid_order_count", "-paid_order_amount", "id")[:10]
    ]

    return {
        "summary": {
            "today_order_count": summary["today_order_count"],
            "today_paid_amount": _money(summary["today_paid_amount"]),
        },
        "low_stock_products": low_stock_products,
        "abnormal_payments": abnormal_payments,
        "trend": trend,
        "top_products": top_products,
    }
