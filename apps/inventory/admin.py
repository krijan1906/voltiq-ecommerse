from django.contrib import admin

from apps.inventory.models import StockHistory


@admin.register(StockHistory)
class StockHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "change",
        "previous_quantity",
        "new_quantity",
        "reason",
        "order",
        "changed_by",
        "created_at",
    )
    list_filter = ("reason", "created_at")
    search_fields = ("product__name", "product__sku", "reference", "order__order_number")
    date_hierarchy = "created_at"
    list_select_related = ("product", "order", "changed_by")
    readonly_fields = (
        "product",
        "change",
        "previous_quantity",
        "new_quantity",
        "reason",
        "reference",
        "order",
        "changed_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
