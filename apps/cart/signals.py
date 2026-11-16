"""Merge a guest cart into the customer's cart after authentication."""
from django.contrib.auth.signals import user_logged_in
from django.db import transaction
from django.dispatch import receiver

from apps.cart.models import Cart


@receiver(user_logged_in)
def merge_guest_cart(sender, request, user, **kwargs):
    # ``login()`` rotates the session key before sending this signal. Use the
    # key captured by get_cart() so the guest cart can still be found.
    session_key = request.session.get("guest_cart_key") or request.session.session_key
    if not session_key:
        return
    guest_cart = (
        Cart.objects.filter(session_key=session_key, user__isnull=True)
        .prefetch_related("items__product")
        .first()
    )
    if not guest_cart:
        request.session.pop("guest_cart_key", None)
        return
    with transaction.atomic():
        user_cart, _ = Cart.objects.get_or_create(user=user)
        for item in guest_cart.items.select_related("product"):
            if not item.product.is_active:
                continue
            existing = user_cart.items.filter(product=item.product).first()
            available = item.product.stock_quantity
            if existing:
                existing.quantity = min(existing.quantity + item.quantity, max(available, existing.quantity))
                existing.save(update_fields=["quantity", "updated_at"])
            else:
                user_cart.items.create(
                    product=item.product,
                    quantity=min(item.quantity, max(available, 1)),
                    price_snapshot=item.product.current_price,
                )
        guest_cart.delete()
        request.session.pop("guest_cart_key", None)
        request.session["cart_merged"] = True
