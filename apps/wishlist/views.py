from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.cart.services import CartError, add_to_cart, remove_cart_item
from apps.products.models import Product
from apps.wishlist.models import Wishlist, WishlistItem


def _wishlist(user):
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return wishlist


def wishlist_detail(request):
    if not request.user.is_authenticated:
        messages.info(request, "Sign in to view your saved products.")
        return redirect(f"{reverse('accounts:login')}?next={request.get_full_path()}")
    wishlist = _wishlist(request.user)
    items = wishlist.items.select_related("product", "product__brand").prefetch_related("product__images")
    return render(request, "wishlist/wishlist.html", {"wishlist": wishlist, "items": items})


@require_POST
def toggle(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "ok": False,
                "auth_required": True,
                "message": "Please sign in to save products.",
                "login_url": f"{reverse('accounts:login')}?next={request.META.get('HTTP_REFERER', '/')}",
            },
            status=401,
        )
    product = get_object_or_404(Product, pk=request.POST.get("product_id"), is_active=True)
    wishlist = _wishlist(request.user)
    item = WishlistItem.objects.filter(wishlist=wishlist, product=product).first()
    if item:
        item.delete()
        added = False
        message = f"{product.name} removed from your wishlist."
    else:
        WishlistItem.objects.create(wishlist=wishlist, product=product)
        added = True
        message = f"{product.name} saved to your wishlist."
    return JsonResponse(
        {
            "ok": True,
            "added": added,
            "wishlist_count": wishlist.item_count,
            "message": message,
        }
    )


@require_POST
def remove_item(request, item_id):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    item = get_object_or_404(WishlistItem, pk=item_id, wishlist__user=request.user)
    item.delete()
    messages.success(request, "Product removed from your wishlist.")
    return redirect("wishlist:detail")


@require_POST
def move_to_cart(request, item_id):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    item = get_object_or_404(
        WishlistItem.objects.select_related("product"), pk=item_id, wishlist__user=request.user
    )
    try:
        add_to_cart(request, item.product, 1)
        item.delete()
        messages.success(request, f"{item.product.name} moved to your cart.")
    except CartError as exc:
        messages.error(request, str(exc))
    return redirect("cart:detail")
