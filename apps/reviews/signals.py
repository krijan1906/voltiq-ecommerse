from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.products.models import Product
from apps.reviews.models import Review


def refresh_product_rating(product_id):
    stats = Review.objects.filter(product_id=product_id, is_approved=True).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    Product.objects.filter(pk=product_id).update(
        rating_avg=round(stats["avg"] or 0, 2), review_count=stats["count"] or 0
    )


@receiver([post_save, post_delete], sender=Review)
def review_changed(sender, instance, **kwargs):
    refresh_product_rating(instance.product_id)
