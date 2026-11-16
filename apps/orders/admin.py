from django.contrib import admin
from django.utils.html import format_html

from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderItem,
    OrderStatusHistory,
    ShippingMethod,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product", "product_name", "sku", "unit_price", "quantity", "line_total")
    readonly_fields = ("product_name", "sku", "line_total")
    autocomplete_fields = ("product",)


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    fields = ("status", "note", "changed_by", "created_at")
    readonly_fields = ("status", "note", "changed_by", "created_at")


class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    extra = 0
    can_delete = False
    fields = ("order", "user", "email", "created_at")
    readonly_fields = ("order", "user", "email", "created_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "full_name",
        "email",
        "status",
        "payment_status",
        "payment_method",
        "total_display",
        "created_at",
    )
    list_filter = ("status", "payment_status", "payment_method", "created_at", "shipping_method")
    search_fields = ("order_number", "email", "full_name", "phone", "tracking_number")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("shipping_method",)
    autocomplete_fields = ("user", "coupon", "shipping_method")
    readonly_fields = (
        "order_number",
        "created_at",
        "updated_at",
        "confirmed_at",
        "shipped_at",
        "delivered_at",
        "cancelled_at",
    )
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    fieldsets = (
        ("Order", {"fields": ("order_number", "user", "status", "payment_status", "payment_method")}),
        ("Customer", {"fields": ("full_name", "email", "phone")}),
        (
            "Shipping address",
            {
                "fields": (
                    "shipping_full_name",
                    "shipping_phone",
                    "shipping_street",
                    "shipping_city",
                    "shipping_district",
                    "shipping_province",
                    "shipping_postal_code",
                    "shipping_country",
                )
            },
        ),
        ("Delivery", {"fields": ("shipping_method", "shipping_method_name", "courier", "tracking_number")}),
        (
            "Totals",
            {
                "fields": (
                    "subtotal",
                    "coupon",
                    "coupon_code",
                    "discount_amount",
                    "shipping_fee",
                    "tax_amount",
                    "total",
                    "currency",
                )
            },
        ),
        ("Notes", {"fields": ("customer_notes", "internal_notes")}),
        (
            "Timeline",
            {
                "fields": (
                    "created_at",
                    "confirmed_at",
                    "shipped_at",
                    "delivered_at",
                    "cancelled_at",
                    "updated_at",
                )
            },
        ),
        ("Request metadata", {"fields": ("ip_address", "user_agent"), "classes": ("collapse",)}),
    )

    @admin.display(description="Total", ordering="total")
    def total_display(self, obj):
        return format_html("<strong>Rs. {:,.0f}</strong>", obj.total)

    def has_delete_permission(self, request, obj=None):
        # Orders are financial records; cancel or refund instead of deleting.
        return request.user.is_superuser


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "sku", "unit_price", "quantity", "line_total", "is_reviewed")
    list_filter = ("is_reviewed",)
    search_fields = ("order__order_number", "product_name", "sku")
    autocomplete_fields = ("order", "product")


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "changed_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order__order_number", "note")
    readonly_fields = ("order", "status", "note", "changed_by", "created_at")
    autocomplete_fields = ("order", "changed_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "value",
        "minimum_order_amount",
        "used_count",
        "usage_limit",
        "valid_from",
        "valid_to",
        "is_active",
    )
    list_filter = ("discount_type", "is_active", "valid_from", "valid_to")
    search_fields = ("code", "description")
    list_editable = ("is_active",)
    readonly_fields = ("used_count", "created_at", "updated_at")
    inlines = [CouponUsageInline]
    fieldsets = (
        (None, {"fields": ("code", "description", "is_active")}),
        ("Discount", {"fields": ("discount_type", "value", "maximum_discount", "minimum_order_amount")}),
        ("Validity", {"fields": ("valid_from", "valid_to", "usage_limit", "per_user_limit", "used_count")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ("coupon", "order", "user", "email", "created_at")
    list_filter = ("coupon", "created_at")
    search_fields = ("coupon__code", "order__order_number", "email")
    readonly_fields = ("coupon", "user", "email", "order", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "charge", "free_over", "delivery_estimate", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"code": ("name",)}
