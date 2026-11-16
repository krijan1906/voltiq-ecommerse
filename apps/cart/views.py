import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from apps.cart.models import Cart
from apps.cart.services import (
    CartError,
    add_to_cart,
    apply_coupon,
    get_cart,
    remove_cart_item,
    remove_coupon,
    update_cart_item,
)
from apps.core.templatetags.voltiq import npr
from apps.orders.models import ShippingMethod
from apps.products.models import Product


def _payload(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST


def _cart_data(cart):
    if cart is not None:
        cart = Cart.objects.filter(pk=cart.pk).prefetch_related("items__product").first()
    return {
        "cart_count": cart.item_count if cart else 0,
        "subtotal": f"{cart.subtotal:.2f}" if cart else "0.00",
        "subtotal_display": npr(cart.subtotal) if cart else "Rs. 0",
        "discount": f"{cart.discount:.2f}" if cart else "0.00",
        "discount_display": npr(cart.discount) if cart else "Rs. 0",
        "shipping": f"{cart.shipping_fee:.2f}" if cart else "0.00",
        "shipping_display": npr(cart.shipping_fee) if cart else "Rs. 0",
        "total": f"{cart.total:.2f}" if cart else "0.00",
        "total_display": npr(cart.total) if cart else "Rs. 0",
        "coupon": cart.coupon.code if cart and cart.coupon else "",
        "free_shipping_remaining": max(
            0,
            int(
                settings.FREE_SHIPPING_THRESHOLD
                - (cart.subtotal if cart else 0)
            ),
        ),
    }


@require_GET
def cart_detail(request):
    cart = get_cart(request)
    items = cart.items.select_related("product", "product__brand").prefetch_related("product__images")
    conflicts = cart.has_stock_conflicts()
    recommended = (
        Product.objects.active()
        .exclude(pk__in=cart.items.values_list("product_id", flat=True))
        .with_listing_data()
        .order_by("-sales_count")[:4]
    )
    context = {
        "cart": cart,
        "items": items,
        "conflicts": conflicts,
        "recommended": recommended,
        "shipping_methods": ShippingMethod.objects.filter(is_active=True)[:3],
        "free_shipping_threshold": settings.FREE_SHIPPING_THRESHOLD,
        "free_shipping_remaining": max(0, settings.FREE_SHIPPING_THRESHOLD - cart.subtotal),
        "free_shipping_progress": min(100, int(cart.subtotal / settings.FREE_SHIPPING_THRESHOLD * 100)) if settings.FREE_SHIPPING_THRESHOLD else 100,
    }
    return render(request, "cart/cart.html", context)


@require_POST
def add_item(request):
    data = _payload(request)
    product = get_object_or_404(Product, pk=data.get("product_id"), is_active=True)
    try:
        add_to_cart(request, product, data.get("quantity", 1))
    except CartError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    cart = get_cart(request)
    return JsonResponse(
        {"ok": True, "message": f"{product.name} added to your cart.", **_cart_data(cart)}
    )


@require_POST
def update_item(request, item_id):
    data = _payload(request)
    try:
        update_cart_item(request, item_id, data.get("quantity", 1))
    except CartError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    cart = get_cart(request, create=False)
    return JsonResponse({"ok": True, "message": "Cart updated.", **_cart_data(cart)})


@require_POST
def remove_item(request, item_id):
    removed = remove_cart_item(request, item_id)
    cart = get_cart(request, create=False)
    return JsonResponse(
        {
            "ok": removed,
            "message": "Item removed from cart." if removed else "Item not found.",
            **_cart_data(cart),
        }
    )


@require_POST
def apply_coupon_view(request):
    data = _payload(request)
    try:
        coupon = apply_coupon(request, data.get("code", ""))
    except CartError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    cart = get_cart(request)
    return JsonResponse(
        {
            "ok": True,
            "message": f"Coupon {coupon.code} applied.",
            "code": coupon.code,
            **_cart_data(cart),
        }
    )


@require_POST
def remove_coupon_view(request):
    remove_coupon(request)
    cart = get_cart(request)
    return JsonResponse({"ok": True, "message": "Coupon removed.", **_cart_data(cart)})


@require_GET
def cart_summary(request):
    cart = get_cart(request, create=False)
    if not cart:
        return JsonResponse({"cart_count": 0, "total_display": "Rs. 0"})
    return JsonResponse(_cart_data(cart))
