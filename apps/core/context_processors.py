"""Global storefront context: navigation, cart badge, wishlist, notifications."""
import datetime

from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch, Sum

from apps.cart.models import Cart, CartItem
from apps.categories.models import Category
from apps.core.models import SiteSetting
from apps.wishlist.models import Wishlist


def _cart_count(request):
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
        else:
            key = request.session.session_key
            cart = Cart.objects.filter(session_key=key, user__isnull=True).first() if key else None
        if not cart:
            return 0, cart
        count = cart.items.aggregate(total=Sum("quantity"))["total"] or 0
        return count, cart
    except Exception:
        return 0, None


def site_context(request):
    site = cache.get("site_setting")
    if site is None:
        try:
            site = SiteSetting.load()
        except Exception:
            site = None
        cache.set("site_setting", site, 600)

    nav_categories = cache.get("nav_categories")
    if nav_categories is None:
        try:
            nav_categories = list(
                Category.objects.filter(is_active=True, parent__isnull=True)
                .prefetch_related(
                    Prefetch("children", queryset=Category.objects.filter(is_active=True).order_by("sort_order", "name"))
                )
                .order_by("sort_order", "name")
            )
        except Exception:
            nav_categories = []
        cache.set("nav_categories", nav_categories, 300)

    cart_count, cart = _cart_count(request)
    wishlist_count = 0
    wishlist_ids = set()
    notifications = []
    unread_notifications = 0
    if request.user.is_authenticated:
        try:
            wishlist = Wishlist.objects.get(user=request.user)
            wishlist_count = wishlist.item_count
            wishlist_ids = set(wishlist.items.values_list("product_id", flat=True))
            notifications = list(request.user.notifications.filter(is_read=False)[:5])
            unread_notifications = request.user.notifications.filter(is_read=False).count()
        except Exception:
            pass

    return {
        "site": site,
        "nav_categories": nav_categories,
        "cart_count": cart_count,
        "cart_obj": cart,
        "wishlist_count": wishlist_count,
        "wishlist_ids": wishlist_ids,
        "nav_notifications": notifications,
        "unread_notifications": unread_notifications,
        "payment_simulation": settings.PAYMENT_SIMULATION,
        "support_email": settings.SUPPORT_EMAIL,
        "site_url": settings.SITE_URL,
        "current_year": datetime.date.today().year,
        "bank_details": {
            "bank_name": settings.BANK_NAME,
            "account_name": settings.BANK_ACCOUNT_NAME,
            "account_number": settings.BANK_ACCOUNT_NUMBER,
            "branch": settings.BANK_BRANCH,
            "swift": settings.BANK_SWIFT,
            "support_note": settings.BANK_SUPPORT_NOTE,
        },
    }
