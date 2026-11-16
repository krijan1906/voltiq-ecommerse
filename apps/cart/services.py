"""Cart persistence and stock-aware mutations (used by web views and APIs)."""
from django.db import transaction

from apps.cart.models import Cart, CartItem
from apps.orders.models import Coupon

MAX_ITEM_QUANTITY = 20


class CartError(Exception):
    pass


def get_cart(request, create=True):
    if request.user.is_authenticated:
        if create:
            cart, _ = Cart.objects.get_or_create(user=request.user)
            return cart
        return Cart.objects.filter(user=request.user).first()

    session = request.session
    if not session.session_key:
        if not create:
            return None
        session.create()
    key = session.session_key
    if create:
        cart, _ = Cart.objects.get_or_create(session_key=key, user__isnull=True)
        # Remember which guest cart belongs to this session. Django rotates the
        # session key on login, so the merge signal cannot rely on
        # request.session.session_key alone.
        if session.get("guest_cart_key") != key:
            session["guest_cart_key"] = key
        return cart
    return Cart.objects.filter(session_key=key, user__isnull=True).first()


def add_to_cart(request, product, quantity=1):
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise CartError("Invalid quantity.")
    if quantity < 1:
        raise CartError("Quantity must be at least 1.")
    if not product.is_active or not product.category.is_active:
        raise CartError("This product is no longer available.")
    if not product.in_stock:
        raise CartError("This product is out of stock.")

    # Create the guest session/cart before opening the transaction. Otherwise a
    # validation error will roll back the session row too, leaving the session
    # middleware with a key that no longer exists (HTTP 400 SessionInterrupted).
    cart = get_cart(request)
    with transaction.atomic():
        item = CartItem.objects.select_for_update().filter(cart=cart, product=product).first()
        current = item.quantity if item else 0
        desired = current + quantity
        max_allowed = product.stock_quantity if not product.allow_backorder else MAX_ITEM_QUANTITY
        max_allowed = min(max_allowed, MAX_ITEM_QUANTITY)
        if desired > max_allowed:
            if max_allowed <= 0:
                raise CartError("This product is out of stock.")
            raise CartError(
                f"Only {max_allowed} unit{'s' if max_allowed != 1 else ''} available"
                + (f" and you already have {current} in your cart." if current else ".")
            )

        if item:
            item.quantity = desired
            item.price_snapshot = product.current_price
            item.save(update_fields=["quantity", "price_snapshot", "updated_at"])
        else:
            item = CartItem.objects.create(
                cart=cart, product=product, quantity=quantity, price_snapshot=product.current_price
            )
        cart.save(update_fields=["updated_at"])
        return item


def update_cart_item(request, item_id, quantity):
    cart = get_cart(request, create=False)
    if not cart:
        raise CartError("Your cart is empty.")
    with transaction.atomic():
        item = (
            CartItem.objects.select_for_update()
            .select_related("product")
            .filter(cart=cart, pk=item_id)
            .first()
        )
        if not item:
            raise CartError("Cart item not found.")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise CartError("Invalid quantity.")
        if quantity <= 0:
            item.delete()
            cart.save(update_fields=["updated_at"])
            return None
        if quantity > MAX_ITEM_QUANTITY:
            raise CartError(f"You can order at most {MAX_ITEM_QUANTITY} units per item.")
        if quantity > item.product.stock_quantity and not item.product.allow_backorder:
            raise CartError(f"Only {item.product.stock_quantity} units are in stock.")
        item.quantity = quantity
        item.price_snapshot = item.product.current_price
        item.save(update_fields=["quantity", "price_snapshot", "updated_at"])
        cart.save(update_fields=["updated_at"])
        return item


def remove_cart_item(request, item_id):
    cart = get_cart(request, create=False)
    if not cart:
        return False
    deleted, _ = CartItem.objects.filter(cart=cart, pk=item_id).delete()
    return bool(deleted)


def apply_coupon(request, code):
    cart = get_cart(request)
    if not cart.items.exists():
        raise CartError("Add products to your cart before applying a coupon.")
    try:
        coupon = Coupon.objects.get(code__iexact=(code or "").strip())
    except Coupon.DoesNotExist:
        raise CartError("That coupon code is not valid.")
    valid, reason = coupon.validate_for(cart.subtotal, request.user)
    if not valid:
        raise CartError(reason)
    cart.coupon = coupon
    cart.save(update_fields=["coupon", "updated_at"])
    return coupon


def remove_coupon(request):
    cart = get_cart(request, create=False)
    if cart:
        cart.coupon = None
        cart.save(update_fields=["coupon", "updated_at"])


def set_shipping_method(request, method):
    cart = get_cart(request)
    cart.shipping_method = method
    cart.save(update_fields=["shipping_method", "updated_at"])
