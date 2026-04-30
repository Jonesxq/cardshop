from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from orders.models import Order, PaymentTransaction
from shop.models import CardSecret, Product


def _money(value):
    return f"{value or Decimal('0.00'):.2f}"


def _product_stock_counts():
    counts = {}
    for row in CardSecret.objects.values("product_id", "status").annotate(count=Count("id")):
        stock = counts.setdefault(
            row["product_id"],
            {
                "available": 0,
                "reserved": 0,
                "sold": 0,
                "void": 0,
            },
        )
        stock[row["status"]] = row["count"]
    return counts


def _paid_order_stats():
    return {
        row["product_id"]: {
            "paid_order_count": row["paid_order_count"],
            "paid_amount": row["paid_amount"],
        }
        for row in Order.objects.filter(status=Order.Status.PAID)
        .values("product_id")
        .annotate(paid_order_count=Count("id"), paid_amount=Coalesce(Sum("amount"), Decimal("0.00")))
    }


def get_dashboard_payload():
    today = timezone.localdate()
    start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    end = start + timezone.timedelta(days=1)

    paid_today = Order.objects.filter(status=Order.Status.PAID, paid_at__gte=start, paid_at__lt=end)
    summary = paid_today.aggregate(
        today_order_count=Count("id"),
        today_paid_amount=Coalesce(Sum("amount"), Decimal("0.00")),
    )
    pending_order_count = Order.objects.filter(status=Order.Status.PENDING).count()
    abnormal_payment_count = PaymentTransaction.objects.exclude(status=PaymentTransaction.Status.SUCCESS).count()

    stock_counts = _product_stock_counts()
    paid_stats = _paid_order_stats()
    products = list(Product.objects.all())
    low_stock_candidates = [
        product for product in products if product.is_active and stock_counts.get(product.id, {}).get("available", 0) <= 5
    ]
    low_stock_product_count = len(low_stock_candidates)

    low_stock_products = [
        {
            "id": product.id,
            "name": product.name,
            "available": stock_counts.get(product.id, {}).get("available", 0),
        }
        for product in sorted(
            low_stock_candidates,
            key=lambda item: (stock_counts.get(item.id, {}).get("available", 0), item.id),
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
            "paid_order_count": paid_stats.get(product.id, {}).get("paid_order_count", 0),
            "paid_amount": _money(paid_stats.get(product.id, {}).get("paid_amount")),
        }
        for product in sorted(
            products,
            key=lambda item: (
                -paid_stats.get(item.id, {}).get("paid_order_count", 0),
                -paid_stats.get(item.id, {}).get("paid_amount", Decimal("0.00")),
                item.id,
            ),
        )[:10]
    ]

    return {
        "summary": {
            "today_order_count": summary["today_order_count"],
            "today_paid_amount": _money(summary["today_paid_amount"]),
            "pending_order_count": pending_order_count,
            "low_stock_product_count": low_stock_product_count,
            "abnormal_payment_count": abnormal_payment_count,
        },
        "low_stock_products": low_stock_products,
        "abnormal_payments": abnormal_payments,
        "trend": trend,
        "top_products": top_products,
    }
