from django.contrib import admin

from apps.wishlist.models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    fields = ("product", "notify_on_restock", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("product",)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "item_count", "created_at", "updated_at")
    search_fields = ("user__email",)
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [WishlistItemInline]

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.item_count


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("wishlist", "product", "notify_on_restock", "created_at")
    list_filter = ("notify_on_restock",)
    search_fields = ("wishlist__user__email", "product__name", "product__sku")
    list_select_related = ("wishlist", "product")
    autocomplete_fields = ("wishlist", "product")
