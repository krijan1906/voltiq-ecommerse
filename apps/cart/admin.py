from django.contrib import admin

from apps.cart.models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("product", "quantity", "price_snapshot", "added_at")
    readonly_fields = ("added_at",)
    autocomplete_fields = ("product",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("owner", "coupon", "shipping_method", "item_count", "subtotal_display", "updated_at")
    search_fields = ("user__email", "session_key")
    list_select_related = ("user", "coupon", "shipping_method")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "coupon", "shipping_method")
    inlines = [CartItemInline]

    @admin.display(description="Owner")
    def owner(self, obj):
        return obj.user.email if obj.user else f"Guest ({obj.session_key or 'no session'})"

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.item_count

    @admin.display(description="Subtotal")
    def subtotal_display(self, obj):
        return f"Rs. {obj.subtotal:,.0f}"


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "quantity", "price_snapshot", "line_total_display", "added_at")
    search_fields = ("cart__user__email", "product__name", "product__sku")
    list_select_related = ("cart", "product")
    autocomplete_fields = ("cart", "product")

    @admin.display(description="Line total")
    def line_total_display(self, obj):
        return f"Rs. {obj.line_total:,.0f}"
