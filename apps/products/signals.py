from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.products.models import Product, ProductImage, ProductSpecification


def invalidate_storefront_cache():
    cache.delete_many(
        [
            "home_featured",
            "home_trending",
            "home_bestsellers",
            "home_latest",
            "home_deals",
            "home_categories",
            "home_brands",
            "home_reviews",
        ]
    )


@receiver([post_save, post_delete], sender=Product)
def product_changed(sender, instance, **kwargs):
    invalidate_storefront_cache()


@receiver([post_save, post_delete], sender=ProductImage)
def product_image_changed(sender, instance, **kwargs):
    invalidate_storefront_cache()


@receiver([post_save, post_delete], sender=ProductSpecification)
def product_spec_changed(sender, instance, **kwargs):
    invalidate_storefront_cache()


@receiver(post_delete, sender=ProductImage)
def delete_product_image_file(sender, instance, **kwargs):
    """Remove the stored file when an image row is deleted."""
    if instance.image:
        try:
            instance.image.delete(save=False)
        except Exception:
            pass
