from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.categories.models import Brand, Category


def invalidate_category_cache():
    cache.delete("nav_categories")


@receiver([post_save, post_delete], sender=Category)
def category_changed(sender, instance, **kwargs):
    invalidate_category_cache()


@receiver([post_save, post_delete], sender=Brand)
def brand_changed(sender, instance, **kwargs):
    invalidate_category_cache()


@receiver(post_delete, sender=Category)
def delete_category_image_file(sender, instance, **kwargs):
    if instance.image:
        try:
            instance.image.delete(save=False)
        except Exception:
            pass


@receiver(post_delete, sender=Brand)
def delete_brand_logo_file(sender, instance, **kwargs):
    if instance.logo:
        try:
            instance.logo.delete(save=False)
        except Exception:
            pass
