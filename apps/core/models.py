from django.db import models


class NewsletterSubscription(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    token = models.CharField(max_length=64, blank=True)
    source = models.CharField(max_length=40, default="footer")
    created_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email


class ContactMessage(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=180)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.email}"


class SiteSetting(models.Model):
    """Singleton store settings editable from the dashboard."""

    store_name = models.CharField(max_length=80, default="Voltiq")
    tagline = models.CharField(max_length=140, default="Premium electronics, powered for life.")
    announcement = models.CharField(
        max_length=200, default="Free delivery across Nepal on orders over Rs. 10,000"
    )
    support_phone = models.CharField(max_length=30, default="+977 980-000-0000")
    support_email = models.EmailField(default="support@voltiq.com.np")
    address = models.CharField(max_length=255, default="Durbar Marg, Kathmandu 44600, Nepal")
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site setting"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return self.store_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
