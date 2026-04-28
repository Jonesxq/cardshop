from django.db.models import Count, Q

from .models import Announcement, Category, Product, SiteConfig


DEFAULT_SITE = {
    "site_name": "AI 发卡商城",
    "logo_url": "",
    "support_contact": "support@example.com",
    "footer_text": "虚拟商品自动发货，购买前请确认商品说明。",
}


def get_site_config():
    config = DEFAULT_SITE.copy()
    for item in SiteConfig.objects.all():
        config[item.key] = item.value
    return config


def get_home_payload():
    products = (
        Product.objects.filter(is_active=True, category__is_active=True)
        .select_related("category")
        .annotate(stock=Count("cards", filter=Q(cards__status="available")))
        .order_by("category__sort_order", "sort_order", "id")
    )
    categories = Category.objects.filter(is_active=True).order_by("sort_order", "id")
    return {
        "site": get_site_config(),
        "announcements": [
            {"id": item.id, "title": item.title, "content": item.content}
            for item in Announcement.objects.filter(is_active=True)[:5]
        ],
        "categories": [
            {"id": item.id, "name": item.name, "slug": item.slug}
            for item in categories
        ],
        "products": [
            {
                "id": product.id,
                "category_id": product.category_id,
                "category_name": product.category.name,
                "name": product.name,
                "description": product.description,
                "price": str(product.price),
                "image_url": product.image_url,
                "stock": product.stock,
                "is_sold_out": product.stock <= 0,
            }
            for product in products
        ],
    }

