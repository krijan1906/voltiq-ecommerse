from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.products.models import Product


class ReviewQuerySet(models.QuerySet):
    def approved(self):
        return self.filter(is_approved=True)


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], help_text="1 to 5 stars"
    )
    title = models.CharField(max_length=140)
    body = models.TextField(max_length=3000)
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True, db_index=True)
    helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReviewQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("product", "user")]
        indexes = [models.Index(fields=["product", "is_approved"])]

    def __str__(self):
        return f"{self.rating}★ {self.product.name} by {self.user.email}"

    @property
    def stars_range(self):
        return range(1, 6)
