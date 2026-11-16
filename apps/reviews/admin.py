from django.contrib import admin
from django.utils.html import format_html

from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "user",
        "stars",
        "title",
        "verified_purchase",
        "is_approved",
        "helpful_count",
        "created_at",
    )
    list_filter = ("is_approved", "is_verified_purchase", "rating", "created_at")
    search_fields = ("product__name", "user__email", "title", "body")
    list_editable = ("is_approved",)
    list_select_related = ("product", "user")
    readonly_fields = ("created_at", "updated_at", "helpful_count")
    autocomplete_fields = ("product", "user")
    actions = ("approve_reviews", "unapprove_reviews")

    @admin.display(description="Rating", ordering="rating")
    def stars(self, obj):
        filled = "★" * obj.rating
        empty = "☆" * (5 - obj.rating)
        return format_html('<span style="color:#f59e0b">{}</span><span style="color:#cbd5e1">{}</span>', filled, empty)

    @admin.display(boolean=True, description="Verified")
    def verified_purchase(self, obj):
        return obj.is_verified_purchase

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        count = queryset.update(is_approved=True)
        for product_id in queryset.values_list("product_id", flat=True).distinct():
            from apps.reviews.signals import refresh_product_rating

            refresh_product_rating(product_id)
        self.message_user(request, f"{count} review(s) approved.")

    @admin.action(description="Unapprove selected reviews")
    def unapprove_reviews(self, request, queryset):
        count = queryset.update(is_approved=False)
        for product_id in queryset.values_list("product_id", flat=True).distinct():
            from apps.reviews.signals import refresh_product_rating

            refresh_product_rating(product_id)
        self.message_user(request, f"{count} review(s) moved to moderation.")
