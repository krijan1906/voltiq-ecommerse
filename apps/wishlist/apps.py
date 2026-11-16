from django.apps import AppConfig


class WishlistConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.wishlist"
    verbose_name = "Wishlists"

    def ready(self):
        from apps.wishlist import signals  # noqa: F401
