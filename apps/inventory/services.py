"""Inventory mutations with row locking, audit trail and restock alerts."""
from django.db import transaction

from apps.inventory.models import StockHistory
from apps.products.models import Product


class StockError(Exception):
    pass


def adjust_stock(product, change, reason, reference="", order=None, user=None):
    """Adjust stock inside a transaction. Caller is responsible for atomicity."""
    locked = Product.objects.select_for_update().get(pk=product.pk)
    previous = locked.stock_quantity
    new_quantity = previous + int(change)
    if new_quantity < 0:
        raise StockError(f"Insufficient stock for {locked.name}.")
    locked.stock_quantity = new_quantity
    locked.save(update_fields=["stock_quantity", "updated_at"])
    StockHistory.objects.create(
        product=locked,
        change=int(change),
        previous_quantity=previous,
        new_quantity=new_quantity,
        reason=reason,
        reference=reference[:120],
        order=order,
        changed_by=user if user and user.is_authenticated else None,
    )
    if previous <= 0 < new_quantity:
        from apps.wishlist.services import notify_restock

        notify_restock(locked)
    product.stock_quantity = new_quantity
    return locked


def set_stock(product, new_quantity, reason=StockHistory.Reason.ADJUSTMENT, reference="", user=None):
    locked = Product.objects.select_for_update().get(pk=product.pk)
    change = int(new_quantity) - locked.stock_quantity
    if change == 0:
        return locked
    return adjust_stock(locked, change, reason, reference=reference, user=user)


@transaction.atomic
def restock_order(order, changed_by=None, reason=StockHistory.Reason.CANCELLATION):
    for item in order.items.select_related("product"):
        if item.product:
            adjust_stock(
                item.product,
                item.quantity,
                reason,
                reference=order.order_number,
                order=order,
                user=changed_by,
            )
