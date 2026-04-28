from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shop.models import Announcement, CardSecret, Category, Product, SiteConfig


class Command(BaseCommand):
    help = "Seed demo categories, products, cards, announcements and an admin user."

    def handle(self, *args, **options):
        User = get_user_model()
        admin, created = User.objects.get_or_create(
            email="admin@example.com",
            defaults={"username": "admin@example.com", "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("Admin12345!")
            admin.save(update_fields=["password"])

        configs = {
            "site_name": ("AI 发卡商城", "站点名称"),
            "support_contact": ("support@example.com", "售后联系方式"),
            "footer_text": ("虚拟商品自动发货，请在购买前确认商品说明。", "页脚说明"),
        }
        for key, (value, label) in configs.items():
            SiteConfig.objects.update_or_create(key=key, defaults={"value": value, "label": label})

        Announcement.objects.get_or_create(
            title="购买须知",
            defaults={
                "content": "下单后请在 15 分钟内完成支付，支付成功后系统会自动展示卡密。",
                "sort_order": 1,
            },
        )

        ai_tools, _ = Category.objects.get_or_create(
            slug="ai-tools",
            defaults={"name": "AI 工具", "sort_order": 1},
        )
        digital, _ = Category.objects.get_or_create(
            slug="digital",
            defaults={"name": "数字权益", "sort_order": 2},
        )

        products = [
            (
                ai_tools,
                "AI 绘图点数包",
                "适用于合规创作场景的绘图点数兑换码，自动发货。",
                "29.90",
                "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=900&q=80",
                ["AI-DRAW-1000-ABCD", "AI-DRAW-1000-EFGH", "AI-DRAW-1000-IJKL"],
            ),
            (
                ai_tools,
                "智能写作月卡",
                "用于个人效率工具的月度兑换码，购买后请及时绑定。",
                "39.90",
                "https://images.unsplash.com/photo-1674027444485-cec3da58eef4?auto=format&fit=crop&w=900&q=80",
                ["WRITE-MONTH-2026-A", "WRITE-MONTH-2026-B", "WRITE-MONTH-2026-C"],
            ),
            (
                digital,
                "云笔记高级兑换码",
                "数字权益示例商品，发货内容为一次性兑换码。",
                "19.90",
                "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80",
                ["NOTE-PRO-001", "NOTE-PRO-002", "NOTE-PRO-003"],
            ),
        ]

        for category, name, description, price, image_url, cards in products:
            product, _ = Product.objects.update_or_create(
                name=name,
                defaults={
                    "category": category,
                    "description": description,
                    "price": price,
                    "image_url": image_url,
                    "is_active": True,
                },
            )
            if not product.cards.exists():
                for raw in cards:
                    card = CardSecret(product=product)
                    card.set_secret(raw)
                    card.save()

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))

