from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.validators import validate_image_upload


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, db_index=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="children", blank=True, null=True
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True, validators=[validate_image_upload])
    icon = models.CharField(
        max_length=40,
        default="chip",
        help_text="Icon key used by the storefront (laptop, phone, monitor, ...).",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "Categories"
        indexes = [models.Index(fields=["is_active", "parent", "sort_order"])]

    def __str__(self):
        return f"{self.parent.name} → {self.name}" if self.parent else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            counter = 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("products:list") + f"?category={self.slug}"

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()

    @property
    def all_product_count(self):
        from apps.products.models import Product

        ids = [self.pk] + list(self.children.values_list("pk", flat=True))
        return Product.objects.filter(category_id__in=ids, is_active=True).count()


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, db_index=True)
    logo = models.ImageField(upload_to="brands/", blank=True, null=True, validators=[validate_image_upload])
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            counter = 2
            while Brand.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("products:list") + f"?brand={self.slug}"

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()
