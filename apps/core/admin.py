from django.contrib import admin

from apps.core.models import ContactMessage, NewsletterSubscription, SiteSetting


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "source", "is_active", "created_at", "unsubscribed_at")
    list_filter = ("is_active", "source", "created_at")
    search_fields = ("email", "name")
    readonly_fields = ("token", "created_at", "unsubscribed_at")
    actions = ("activate_subscribers", "deactivate_subscribers")

    @admin.action(description="Mark selected subscribers as active")
    def activate_subscribers(self, request, queryset):
        count = queryset.update(is_active=True, unsubscribed_at=None)
        self.message_user(request, f"{count} subscriber(s) reactivated.")

    @admin.action(description="Unsubscribe selected subscribers")
    def deactivate_subscribers(self, request, queryset):
        from django.utils import timezone

        count = queryset.update(is_active=False, unsubscribed_at=timezone.now())
        self.message_user(request, f"{count} subscriber(s) unsubscribed.")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "subject", "message")
    list_editable = ("status",)
    readonly_fields = ("created_at",)
    actions = ("mark_in_progress", "mark_resolved")

    @admin.action(description="Mark selected messages as in progress")
    def mark_in_progress(self, request, queryset):
        count = queryset.update(status=ContactMessage.Status.IN_PROGRESS)
        self.message_user(request, f"{count} message(s) marked in progress.")

    @admin.action(description="Mark selected messages as resolved")
    def mark_resolved(self, request, queryset):
        count = queryset.update(status=ContactMessage.Status.RESOLVED)
        self.message_user(request, f"{count} message(s) marked resolved.")


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("store_name", "support_email", "support_phone", "updated_at")
    fieldsets = (
        ("Store", {"fields": ("store_name", "tagline", "announcement")}),
        ("Support", {"fields": ("support_phone", "support_email", "address")}),
        ("Social", {"fields": ("facebook_url", "instagram_url", "youtube_url", "tiktok_url")}),
        ("Metadata", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
