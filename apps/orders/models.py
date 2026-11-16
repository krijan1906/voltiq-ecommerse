"""Orders, coupons, shipping methods and order lifecycle."""
import secrets
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.products.models import Product


def money(value):
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_order_number():
    date = timezone.localtime().strftime("%y%m%d")
    for _ in range(20):
        candidate = f"VQ-{date}-{secrets.token_hex(3).upper()}"
        if not Order.objects.filter(order_number=candidate).exists():
            return candidate
    return f"VQ-{date}-{secrets.token_hex(4).upper()}"


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed amount"

    code = models.CharField(max_length=40, unique=True, db_index=True)
    description = models.CharField(max_length=200, blank=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    minimum_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maximum_discount = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True, help_text="Cap for percentage coupons"
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(blank=True, null=True)
    usage_limit = models.PositiveIntegerField(blank=True, null=True, help_text="Total redemptions allowed")
    per_user_limit = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return bool(self.valid_to and self.valid_to < timezone.now())

    def validate_for(self, subtotal, user=None, email=""):
        now = timezone.now()
        if not self.is_active:
            return False, "This coupon is no longer active."
        if self.valid_from and self.valid_from > now:
            return False, "This coupon is not active yet."
        if self.valid_to and self.valid_to < now:
            return False, "This coupon has expired."
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False, "This coupon has reached its usage limit."
        if subtotal < self.minimum_order_amount:
            return False, f"A minimum order of Rs. {self.minimum_order_amount:,.0f} is required."
        if user and user.is_authenticated and self.per_user_limit:
            used = CouponUsage.objects.filter(coupon=self, user=user).count()
            if used >= self.per_user_limit:
                return False, "You have already used this coupon."
        elif email and self.per_user_limit:
            used = CouponUsage.objects.filter(coupon=self, email__iexact=email).count()
            if used >= self.per_user_limit:
                return False, "This coupon has already been used with this email."
        return True, ""

    def calculate_discount(self, subtotal):
        subtotal = money(subtotal)
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = subtotal * self.value / Decimal("100")
        else:
            discount = self.value
        if self.maximum_discount is not None:
            discount = min(discount, self.maximum_discount)
        return money(min(discount, subtotal))


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="usages")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="coupon_usages"
    )
    email = models.EmailField(blank=True)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="coupon_usages")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.coupon.code} → {self.order.order_number}"


class ShippingMethod(models.Model):
    name = models.CharField(max_length=80)
    code = models.SlugField(max_length=40, unique=True)
    description = models.CharField(max_length=200, blank=True)
    charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_over = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Free when the cart subtotal reaches this amount.",
    )
    min_days = models.PositiveIntegerField(default=2)
    max_days = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "charge"]

    def __str__(self):
        return self.name

    def fee_for(self, subtotal):
        if self.free_over is not None and subtotal >= self.free_over:
            return Decimal("0")
        return money(self.charge)

    @property
    def delivery_estimate(self):
        if self.min_days == self.max_days:
            return f"{self.min_days} day{'s' if self.min_days != 1 else ''}"
        return f"{self.min_days}–{self.max_days} days"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"

    class PaymentMethod(models.TextChoices):
        ESEWA = "esewa", "eSewa"
        KHALTI = "khalti", "Khalti"
        COD = "cod", "Cash on Delivery"
        BANK = "bank", "Bank Transfer"

    order_number = models.CharField(max_length=30, unique=True, db_index=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="orders"
    )
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=20)
    full_name = models.CharField(max_length=120)

    shipping_full_name = models.CharField(max_length=120)
    shipping_phone = models.CharField(max_length=20)
    shipping_street = models.CharField(max_length=255)
    shipping_city = models.CharField(max_length=80)
    shipping_district = models.CharField(max_length=80)
    shipping_province = models.CharField(max_length=40)
    shipping_postal_code = models.CharField(max_length=10, blank=True)
    shipping_country = models.CharField(max_length=50, default="Nepal")

    shipping_method = models.ForeignKey(
        ShippingMethod, on_delete=models.SET_NULL, blank=True, null=True, related_name="orders"
    )
    shipping_method_name = models.CharField(max_length=80, blank=True)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, blank=True, null=True, related_name="orders")
    coupon_code = models.CharField(max_length=40, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="NPR")

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_status = models.CharField(
        max_length=30, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True
    )
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)

    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    courier = models.CharField(max_length=80, blank=True)

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_order_number()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("orders:detail", kwargs={"order_number": self.order_number})

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def is_paid(self):
        return self.payment_status == self.PaymentStatus.PAID

    @property
    def can_cancel(self):
        return self.status in {
            self.Status.PENDING,
            self.Status.CONFIRMED,
            self.Status.PROCESSING,
        }

    @property
    def can_pay(self):
        return (
            self.payment_status in {self.PaymentStatus.PENDING, self.PaymentStatus.FAILED}
            and self.status not in {self.Status.CANCELLED, self.Status.REFUNDED, self.Status.DELIVERED}
        )

    @property
    def status_index(self):
        flow = [
            self.Status.PENDING,
            self.Status.CONFIRMED,
            self.Status.PROCESSING,
            self.Status.SHIPPED,
            self.Status.OUT_FOR_DELIVERY,
            self.Status.DELIVERED,
        ]
        try:
            return flow.index(self.status)
        except ValueError:
            return -1

    def set_status(self, status, note="", changed_by=None):
        old = self.status
        if old == status:
            return
        self.status = status
        now = timezone.now()
        if status == self.Status.CONFIRMED:
            self.confirmed_at = now
        elif status == self.Status.SHIPPED:
            self.shipped_at = now
        elif status == self.Status.DELIVERED:
            self.delivered_at = now
            if self.payment_method == self.PaymentMethod.COD:
                self.payment_status = self.PaymentStatus.PAID
        elif status == self.Status.CANCELLED:
            self.cancelled_at = now
        self.save()
        OrderStatusHistory.objects.create(order=self, status=status, note=note, changed_by=changed_by)

    def recalculate(self, commit=True):
        self.subtotal = money(sum((item.line_total for item in self.items.all()), Decimal("0")))
        self.total = money(
            max(
                Decimal("0"),
                self.subtotal - self.discount_amount + self.shipping_fee + self.tax_amount,
            )
        )
        if commit:
            self.save(update_fields=["subtotal", "total", "updated_at"])
        return self.total

    def recalc_discount(self, commit=False):
        if self.coupon:
            self.discount_amount = self.coupon.calculate_discount(self.subtotal)
        if commit:
            self.save(update_fields=["discount_amount", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, blank=True, null=True, related_name="order_items")
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=60)
    image_url = models.CharField(max_length=500, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_reviewed = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"

    def save(self, *args, **kwargs):
        self.line_total = money(self.unit_price * self.quantity)
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=30, choices=Order.Status.choices)
    note = models.CharField(max_length=300, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="order_status_changes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "Order status history"

    def __str__(self):
        return f"{self.order.order_number}: {self.get_status_display()}"
