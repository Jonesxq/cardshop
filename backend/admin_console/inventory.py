from dataclasses import dataclass

from django.db import transaction

from shop.models import CardSecret, Product


@dataclass(frozen=True)
class ImportRow:
    row_number: int
    value: str
    status: str


def parse_card_text(text):
    rows = []
    empty_count = 0
    same_batch_duplicate_count = 0
    seen = set()

    for index, raw_value in enumerate((text or "").split("\n"), start=1):
        value = raw_value.strip()
        if not value:
            empty_count += 1
            rows.append(ImportRow(row_number=index, value="", status="empty"))
        elif value in seen:
            same_batch_duplicate_count += 1
            rows.append(ImportRow(row_number=index, value=value, status="same_batch_duplicate"))
        else:
            seen.add(value)
            rows.append(ImportRow(row_number=index, value=value, status="candidate"))

    return rows, empty_count, same_batch_duplicate_count


def _existing_card_values(product):
    values = set()
    for card in CardSecret.objects.filter(product=product):
        values.add(card.get_secret())
    return values


def _serialize_rejected_samples(rows):
    return [
        {
            "row_number": row.row_number,
            "value": row.value,
            "status": row.status,
        }
        for row in rows
        if row.status != "valid"
    ][:10]


def build_import_preview(product, cards):
    rows, empty_count, same_batch_duplicate_count = parse_card_text(cards)
    existing_values = _existing_card_values(product)
    valid_values = []
    existing_duplicate_count = 0
    resolved_rows = []

    for row in rows:
        if row.status != "candidate":
            resolved_rows.append(row)
        elif row.value in existing_values:
            existing_duplicate_count += 1
            resolved_rows.append(ImportRow(row.row_number, row.value, "existing_duplicate"))
        else:
            valid_values.append(row.value)
            resolved_rows.append(ImportRow(row.row_number, row.value, "valid"))

    return {
        "product_id": product.id,
        "total_rows": len(rows),
        "valid_count": len(valid_values),
        "empty_count": empty_count,
        "same_batch_duplicate_count": same_batch_duplicate_count,
        "existing_duplicate_count": existing_duplicate_count,
        "rejected_samples": _serialize_rejected_samples(resolved_rows),
        "valid_values": valid_values,
    }


def without_valid_values(preview):
    result = dict(preview)
    result.pop("valid_values", None)
    return result


def commit_card_import(product_id, cards):
    with transaction.atomic():
        product = Product.objects.select_for_update().get(id=product_id)
        preview = build_import_preview(product, cards)
        card_objects = []
        for value in preview["valid_values"]:
            card = CardSecret(product=product)
            card.set_secret(value)
            card_objects.append(card)
        CardSecret.objects.bulk_create(card_objects)

    result = without_valid_values(preview)
    result["created_count"] = len(card_objects)
    return product, result
