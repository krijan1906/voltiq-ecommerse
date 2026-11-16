from django.contrib import admin
from django.utils.html import format_html

from apps.categories.models import Brand, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "product_count", "icon", "is_active", "is_featured", "sort_order")
    list_filter = ("is_active", "is_featured", "parent")
    search_fields = ("name", "description")
    list_editable = ("is_active", "is_featured", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("parent",)
    fieldsets = (
        (None, {"fields": ("name", "slug", "parent", "icon")}),
        ("Content", {"fields": ("description", "image")}),
        ("Visibility", {"fields": ("is_active", "is_featured", "sort_order")}),
    )

    @admin.display(description="Products", ordering="products__count")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "logo_preview", "product_count", "website", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured")
    search_fields = ("name", "description")
    list_editable = ("is_active", "is_featured")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "logo")}),
        ("Content", {"fields": ("description", "website")}),
        ("Visibility", {"fields": ("is_active", "is_featured")}),
    )

    @admin.display(description="Logo")
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" alt="" style="height:28px;border-radius:4px">', obj.logo.url)
        return "—"

    @admin.display(description="Products", ordering="products__count")
    def product_count(self, obj):
        return obj.products.count()
