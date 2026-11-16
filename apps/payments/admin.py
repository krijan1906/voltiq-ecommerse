from django.contrib import admin
from django.utils.html import format_html

from apps.payments.models import Payment, PaymentTransaction


class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    can_delete = False
    fields = ("event", "status", "message", "ip_address", "created_at")
    readonly_fields = ("event", "status", "message", "ip_address", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_ref",
        "order",
        "gateway",
        "amount_display",
        "status",
        "verified",
        "attempt_number",
        "initiated_at",
    )
    list_filter = ("gateway", "status", "is_verified", "currency")
    search_fields = ("transaction_ref", "gateway_ref", "order__order_number", "order__email")
    date_hierarchy = "initiated_at"
    list_select_related = ("order",)
    readonly_fields = (
        "order",
        "gateway",
        "amount",
        "currency",
        "status",
        "transaction_ref",
        "gateway_ref",
        "gateway_payload",
        "verification_payload",
        "is_verified",
        "attempt_number",
        "initiated_at",
        "updated_at",
        "completed_at",
        "failed_reason",
        "refunded_at",
    )
    inlines = [PaymentTransactionInline]

    @admin.display(description="Amount", ordering="amount")
    def amount_display(self, obj):
        return format_html("Rs. {:,.2f}", obj.amount)

    @admin.display(boolean=True, description="Verified")
    def verified(self, obj):
        return obj.is_verified

    def has_add_permission(self, request):
        # Payments are only created by the checkout and gateway verification flows.
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("payment", "event", "status", "message", "ip_address", "created_at")
    list_filter = ("event", "created_at")
    search_fields = ("payment__transaction_ref", "payment__order__order_number", "message")
    readonly_fields = (
        "payment",
        "event",
        "status",
        "message",
        "request_data",
        "response_data",
        "ip_address",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
