import csv
import io
from decimal import Decimal

from django.db import transaction

from .models import CardSecret, Category, Product


CODEX_CATEGORY_NAME = "Codex"
CODEX_CATEGORY_SLUG = "codex"
CODEX_PRODUCT_NAME = "Codex 卡密"
DEFAULT_CODEX_DESCRIPTION = "Codex 卡密自动发货，购买后请在订单查询页查看交付内容。"


def parse_card_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _decode_upload(uploaded_file):
    content = uploaded_file.read()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def parse_uploaded_cards(uploaded_file):
    if not uploaded_file:
        return []
    text = _decode_upload(uploaded_file)
    filename = (uploaded_file.name or "").lower()
    if filename.endswith(".csv"):
        rows = csv.reader(io.StringIO(text))
        cards = []
        for row in rows:
            first_value = next((cell.strip() for cell in row if cell.strip()), "")
            if first_value:
                cards.append(first_value)
        return cards
    return parse_card_lines(text)


def normalize_cards(*sources):
    seen = set()
    unique = []
    duplicate_count = 0
    for source in sources:
        for raw in source:
            card = raw.strip()
            if not card:
                continue
            if card in seen:
                duplicate_count += 1
                continue
            seen.add(card)
            unique.append(card)
    return unique, duplicate_count


def get_or_create_codex_product(*, price, description, image_url="", is_active=True):
    category, _ = Category.objects.get_or_create(
        slug=CODEX_CATEGORY_SLUG,
        defaults={"name": CODEX_CATEGORY_NAME, "sort_order": 0, "is_active": True},
    )
    if not category.is_active:
        category.is_active = True
        category.save(update_fields=["is_active"])

    product = Product.objects.filter(name=CODEX_PRODUCT_NAME).order_by("id").first()
    if product is None:
        product = Product(name=CODEX_PRODUCT_NAME, category=category)

    product.category = category
    product.price = Decimal(str(price)).quantize(Decimal("0.01"))
    product.description = description or DEFAULT_CODEX_DESCRIPTION
    product.image_url = image_url or ""
    product.is_active = is_active
    product.sort_order = 0
    product.save()
    return product


def existing_codex_card_values(product):
    values = set()
    for card in CardSecret.objects.filter(product=product):
        try:
            values.add(card.get_secret())
        except Exception:
            continue
    return values


@transaction.atomic
def import_codex_cards(*, price, description, image_url="", is_active=True, pasted_cards="", uploaded_file=None):
    pasted = parse_card_lines(pasted_cards)
    uploaded = parse_uploaded_cards(uploaded_file)
    incoming_cards, same_batch_duplicates = normalize_cards(pasted, uploaded)
    product = get_or_create_codex_product(
        price=price,
        description=description,
        image_url=image_url,
        is_active=is_active,
    )

    existing_values = existing_codex_card_values(product)
    cards_to_create = []
    existing_duplicates = 0
    for raw in incoming_cards:
        if raw in existing_values:
            existing_duplicates += 1
            continue
        card = CardSecret(product=product)
        card.set_secret(raw)
        cards_to_create.append(card)
        existing_values.add(raw)

    CardSecret.objects.bulk_create(cards_to_create)
    return {
        "product": product,
        "pasted_count": len(pasted),
        "uploaded_count": len(uploaded),
        "input_count": len(pasted) + len(uploaded),
        "created_count": len(cards_to_create),
        "skipped_duplicate_count": same_batch_duplicates + existing_duplicates,
        "same_batch_duplicate_count": same_batch_duplicates,
        "existing_duplicate_count": existing_duplicates,
    }
