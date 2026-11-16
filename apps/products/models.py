"""Catalogue models: products, images, dynamic specifications."""
import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify

from apps.categories.models import Brand, Category
from apps.core.validators import validate_image_upload


def product_image_path(instance, filename):
    sku = getattr(instance.product, "sku", "product")
    return f"products/{sku}/{uuid.uuid4().hex}_{filename}"


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, category__is_active=True)

    def featured(self):
        return self.active().filter(is_featured=True)

    def in_stock(self):
        return self.active().filter(stock_quantity__gt=0)

    def on_sale(self):
        return self.active().filter(discount_price__isnull=False, discount_price__gt=0)

    def with_listing_data(self):
        return self.select_related("category", "brand").prefetch_related("images")

    def search(self, query):
        query = (query or "").strip()
        if not query:
            return self
        return self.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(category__name__icontains=query)
            | Q(processor__icontains=query)
            | Q(gpu__icontains=query)
            | Q(specifications__value__icontains=query)
        ).distinct()


class ProductManager(models.Manager.from_queryset(ProductQuerySet)):
    pass


class Product(models.Model):
    class Condition(models.TextChoices):
        NEW = "new", "New"
        REFURBISHED = "refurbished", "Refurbished"
        OPEN_BOX = "open_box", "Open Box"

    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=240, unique=True, blank=True, db_index=True)
    sku = models.CharField(max_length=60, unique=True, db_index=True, help_text="Unique stock keeping unit")
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField()
    highlights = models.TextField(
        blank=True, help_text="One key selling point per line. Displayed as a bullet list."
    )

    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    discount_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Sale price. Leave empty when not discounted.",
    )
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True, help_text="Internal cost (staff only)"
    )

    stock_quantity = models.PositiveIntegerField(default=0, db_index=True)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    warranty_info = models.CharField(max_length=200, blank=True, default="1 Year Warranty")
    condition = models.CharField(max_length=20, choices=Condition.choices, default=Condition.NEW)
    color = models.CharField(max_length=60, blank=True)

    # Denormalised facets used by filters (kept in sync via dashboard/specs).
    processor = models.CharField(max_length=120, blank=True, db_index=True)
    ram = models.CharField(max_length=40, blank=True, db_index=True)
    storage = models.CharField(max_length=60, blank=True, db_index=True)
    gpu = models.CharField(max_length=120, blank=True, db_index=True)
    display_size = models.CharField(max_length=40, blank=True)
    operating_system = models.CharField(max_length=60, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    free_shipping = models.BooleanField(default=True)
    allow_backorder = models.BooleanField(default=False)

    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0, db_index=True)
    review_count = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0, db_index=True)
    view_count = models.PositiveIntegerField(default=0)

    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "category", "-created_at"]),
            models.Index(fields=["is_active", "brand"]),
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["is_active", "rating_avg"]),
            models.Index(fields=["is_active", "sales_count"]),
            models.Index(fields=["price"]),
            models.Index(fields=["discount_price"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:220]
            slug = base
            counter = 2
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        if self.sku:
            self.sku = self.sku.strip().upper()
        if self.discount_price and self.discount_price >= self.price:
            self.discount_price = None
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"slug": self.slug})

    @property
    def current_price(self):
        if self.discount_price and self.discount_price < self.price:
            return self.discount_price
        return self.price

    @property
    def has_discount(self):
        return bool(self.discount_price and self.discount_price < self.price)

    @property
    def discount_percent(self):
        if not self.has_discount or not self.price:
            return 0
        return int(round((self.price - self.discount_price) / self.price * 100))

    @property
    def savings(self):
        if not self.has_discount:
            return Decimal("0")
        return self.price - self.discount_price

    @property
    def in_stock(self):
        return self.stock_quantity > 0 or self.allow_backorder

    @property
    def is_low_stock(self):
        return 0 < self.stock_quantity <= self.low_stock_threshold

    @property
    def stock_label(self):
        if self.stock_quantity <= 0:
            return "Backorder" if self.allow_backorder else "Out of stock"
        if self.is_low_stock:
            return f"Only {self.stock_quantity} left"
        return "In stock"

    @property
    def primary_image(self):
        images = list(self.images.all())
        if not images:
            return None
        for img in images:
            if img.is_primary:
                return img
        return images[0]

    @property
    def primary_image_url(self):
        image = self.primary_image
        if image and image.image:
            try:
                return image.image.url
            except ValueError:
                return ""
        return ""

    @property
    def highlight_list(self):
        return [line.strip() for line in self.highlights.splitlines() if line.strip()]

    def related_products(self, limit=8):
        return (
            Product.objects.active()
            .filter(Q(category=self.category) | Q(brand=self.brand))
            .exclude(pk=self.pk)
            .with_listing_data()
            .order_by("-rating_avg", "-sales_count")[:limit]
        )

    def is_wishlisted_by(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.wishlist_items.filter(wishlist__user=user).exists()


class SpecificationField(models.Model):
    """Admin-defined specification schema per category (no hardcoding)."""

    class InputType(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        SELECT = "select", "Select"

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="spec_fields")
    label = models.CharField(max_length=80)
    key = models.SlugField(max_length=80, blank=True)
    unit = models.CharField(max_length=30, blank=True, help_text="e.g. GB, inches, mAh")
    input_type = models.CharField(max_length=20, choices=InputType.choices, default=InputType.TEXT)
    options = models.CharField(
        max_length=500, blank=True, help_text="Comma separated options for select inputs"
    )
    is_filterable = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "label"]
        unique_together = [("category", "key")]

    def __str__(self):
        return f"{self.category.name}: {self.label}"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = slugify(self.label)[:80]
        super().save(*args, **kwargs)

    @property
    def option_list(self):
        return [o.strip() for o in self.options.split(",") if o.strip()]


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specifications")
    field = models.ForeignKey(
        SpecificationField, on_delete=models.SET_NULL, blank=True, null=True, related_name="values"
    )
    name = models.CharField(max_length=100)
    key = models.SlugField(max_length=100, blank=True)
    value = models.CharField(max_length=255)
    unit = models.CharField(max_length=30, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        indexes = [models.Index(fields=["key", "value"])]

    def __str__(self):
        return f"{self.name}: {self.value}"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = slugify(self.name)[:100]
        super().save(*args, **kwargs)

    @property
    def display_value(self):
        return f"{self.value} {self.unit}".strip()


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_image_path, validators=[validate_image_upload])
    alt_text = models.CharField(max_length=160, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "sort_order", "id"]

    def __str__(self):
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(
                is_primary=False
            )
        if not self.pk and not ProductImage.objects.filter(product=self.product).exists():
            self.is_primary = True
        super().save(*args, **kwargs)
