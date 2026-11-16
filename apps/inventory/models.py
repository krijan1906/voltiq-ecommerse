from django.conf import settings
from django.db import models

from apps.products.models import Product


class StockHistory(models.Model):
    class Reason(models.TextChoices):
        RESTOCK = "restock", "Restock"
        SALE = "sale", "Sale"
        RETURN = "return", "Customer return"
        ADJUSTMENT = "adjustment", "Manual adjustment"
        DAMAGE = "damage", "Damage / loss"
        CANCELLATION = "cancellation", "Order cancellation"
        SEED = "seed", "Initial stock"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_history")
    change = models.IntegerField(help_text="Positive for added stock, negative for deductions")
    previous_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=30, choices=Reason.choices, default=Reason.ADJUSTMENT)
    reference = models.CharField(max_length=120, blank=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, blank=True, null=True, related_name="stock_changes"
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="stock_changes"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Stock history"
        indexes = [models.Index(fields=["product", "-created_at"])]

    def __str__(self):
        return f"{self.product.sku}: {self.change:+d} ({self.get_reason_display()})"
