from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.html import format_html

from apps.accounts.models import (
    Address,
    CustomerProfile,
    EmailVerificationToken,
    Notification,
    User,
)


class VoltiqUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "role")


class VoltiqUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ("label", "full_name", "phone", "city", "district", "province", "is_default")
    show_change_link = True


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = VoltiqUserChangeForm
    add_form = VoltiqUserCreationForm
    inlines = [AddressInline]
    list_display = (
        "email",
        "full_name",
        "role",
        "is_email_verified",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser", "is_email_verified", "is_suspended")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login", "email_verified_at", "last_login_ip")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name", "phone", "avatar")}),
        (
            "Permissions",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_email_verified",
                    "email_verified_at",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Moderation", {"fields": ("is_suspended", "suspension_reason")}),
        ("Preferences", {"fields": ("newsletter_opt_in",)}),
        ("Metadata", {"fields": ("date_joined", "last_login", "last_login_ip")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="Name", ordering="first_name")
    def full_name(self, obj):
        return obj.get_full_name()


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "marketing_opt_in", "loyalty_points", "created_at")
    list_filter = ("marketing_opt_in",)
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "label", "city", "district", "province", "is_default")
    list_filter = ("province", "address_type", "is_default", "country")
    search_fields = ("full_name", "user__email", "phone", "street_address", "city", "district")
    autocomplete_fields = ("user",)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "created_at", "expires_at", "is_used")
    search_fields = ("user__email", "token")
    readonly_fields = ("token", "created_at", "used_at")
    autocomplete_fields = ("user",)

    @admin.display(boolean=True, description="Used")
    def is_used(self, obj):
        return obj.used_at is not None


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    search_fields = ("user__email", "title", "message")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user",)
    actions = ("mark_read", "mark_unread")

    @admin.action(description="Mark selected notifications as read")
    def mark_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"{updated} notification(s) marked as read.")

    @admin.action(description="Mark selected notifications as unread")
    def mark_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"{updated} notification(s) marked as unread.")
