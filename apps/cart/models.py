"""Session-backed guest carts and persistent customer carts."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.orders.models import Coupon, ShippingMethod
from apps.products.models import Product


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True, related_name="cart"
    )
    session_key = models.CharField(max_length=64, unique=True, blank=True, null=True, db_index=True)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, blank=True, null=True, related_name="carts")
    shipping_method = models.ForeignKey(ShippingMethod, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        owner = self.user.email if self.user else f"guest:{self.session_key}"
        return f"Cart<{owner}>"

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal("0"))

    @property
    def discount(self):
        if not self.coupon:
            return Decimal("0")
        ok, _ = self.coupon.validate_for(self.subtotal, self.user)
        return self.coupon.calculate_discount(self.subtotal) if ok else Decimal("0")

    @property
    def shipping_fee(self):
        if self.shipping_method:
            return self.shipping_method.fee_for(self.subtotal)
        if self.subtotal >= settings.FREE_SHIPPING_THRESHOLD:
            return Decimal("0")
        return Decimal(str(settings.DEFAULT_SHIPPING_FEE))

    @property
    def total(self):
        return max(Decimal("0"), self.subtotal - self.discount + self.shipping_fee)

    def has_stock_conflicts(self):
        return [item for item in self.items.all() if item.quantity > item.product.stock_quantity]

    def clear(self):
        self.items.all().delete()
        self.coupon = None
        self.save(update_fields=["coupon", "updated_at"])


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    price_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("cart", "product")]
        ordering = ["added_at"]

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"

    @property
    def unit_price(self):
        return self.product.current_price

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def exceeds_stock(self):
        return self.quantity > self.product.stock_quantity
