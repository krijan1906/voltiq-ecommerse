from django.contrib import admin
from django.utils.html import format_html

from apps.products.models import (
    Product,
    ProductImage,
    ProductSpecification,
    SpecificationField,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "is_primary", "sort_order", "preview")
    readonly_fields = ("preview",)

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" alt="" style="height:48px;border-radius:4px">', obj.image.url)
        return "—"


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 0
    fields = ("field", "name", "value", "unit", "sort_order")
    autocomplete_fields = ("field",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "category",
        "brand",
        "price_display",
        "stock_quantity",
        "is_active",
        "is_featured",
        "rating_avg",
    )
    list_filter = (
        "is_active",
        "is_featured",
        "condition",
        "category",
        "brand",
        "free_shipping",
        "allow_backorder",
    )
    search_fields = ("name", "sku", "brand__name", "category__name", "processor", "gpu")
    list_select_related = ("category", "brand")
    list_editable = ("is_active", "is_featured")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("rating_avg", "review_count", "sales_count", "view_count", "created_at", "updated_at")
    autocomplete_fields = ("brand", "category")
    inlines = [ProductImageInline, ProductSpecificationInline]
    date_hierarchy = "created_at"
    fieldsets = (
        ("Identity", {"fields": ("name", "slug", "sku", "brand", "category", "condition", "color")}),
        ("Content", {"fields": ("short_description", "description", "highlights", "warranty_info")}),
        (
            "Pricing",
            {"fields": ("price", "discount_price", "cost_price", "free_shipping")},
        ),
        (
            "Inventory",
            {"fields": ("stock_quantity", "low_stock_threshold", "allow_backorder")},
        ),
        (
            "Specifications",
            {
                "fields": ("processor", "ram", "storage", "gpu", "display_size", "operating_system"),
                "classes": ("collapse",),
            },
        ),
        ("Visibility", {"fields": ("is_active", "is_featured")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
        ("Metrics", {"fields": ("rating_avg", "review_count", "sales_count", "view_count", "created_at", "updated_at")}),
    )

    @admin.display(description="Price", ordering="price")
    def price_display(self, obj):
        if obj.has_discount:
            return format_html(
                '<strong>Rs. {:,.0f}</strong><br><s style="color:#94a3b8">Rs. {:,.0f}</s>',
                obj.current_price,
                obj.price,
            )
        return format_html("Rs. {:,.0f}", obj.price)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "image", "is_primary", "sort_order", "created_at")
    list_filter = ("is_primary",)
    search_fields = ("product__name", "product__sku", "alt_text")
    autocomplete_fields = ("product",)
    readonly_fields = ("created_at",)


@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ("product", "name", "value", "unit", "sort_order")
    list_filter = ("unit",)
    search_fields = ("product__name", "product__sku", "name", "value")
    autocomplete_fields = ("product", "field")


@admin.register(SpecificationField)
class SpecificationFieldAdmin(admin.ModelAdmin):
    list_display = ("label", "category", "key", "unit", "input_type", "is_filterable", "sort_order")
    list_filter = ("category", "input_type", "is_filterable")
    search_fields = ("label", "key", "category__name")
    list_editable = ("sort_order",)
    autocomplete_fields = ("category",)
