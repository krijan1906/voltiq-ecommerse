"""Wishlist helpers and restock notifications."""
from apps.accounts.models import Notification
from apps.wishlist.models import WishlistItem


def notify_restock(product):
    items = (
        WishlistItem.objects.filter(product=product, notify_on_restock=True)
        .select_related("wishlist__user")
    )
    notifications = []
    for item in items:
        notifications.append(
            Notification(
                user=item.wishlist.user,
                title="Back in stock",
                message=f"{product.name} is available again. Grab it before it sells out.",
                url=product.get_absolute_url(),
                kind=Notification.Kind.WISHLIST,
            )
        )
    if notifications:
        Notification.objects.bulk_create(notifications)
    return len(notifications)
