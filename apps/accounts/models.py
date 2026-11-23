"""Custom user, customer profile, addresses and notifications."""
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.validators import validate_image_upload

phone_validator = RegexValidator(
    regex=r"^\+?[0-9\s\-()]{7,20}$",
    message="Enter a valid phone number (7-20 digits, may start with +).",
)


def avatar_upload_path(instance, filename):
    return f"avatars/{instance.pk or 'new'}/{uuid.uuid4().hex}_{filename}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_email_verified", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        STAFF = "staff", "Staff"
        ADMIN = "admin", "Administrator"

    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True, validators=[validate_image_upload])
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER, db_index=True)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    newsletter_opt_in = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["is_email_verified"]),
        ]

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.email.lower().strip() if self.email else self.email
        if self.role in {self.Role.STAFF, self.Role.ADMIN}:
            self.is_staff = True

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()
        if self.role in {self.Role.STAFF, self.Role.ADMIN}:
            self.is_staff = True
        super().save(*args, **kwargs)

    def get_full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email.split("@")[0].title()

    def get_short_name(self):
        return self.first_name or self.email.split("@")[0]

    @property
    def initials(self):
        parts = [p for p in [self.first_name, self.last_name] if p]
        if parts:
            return "".join(p[0] for p in parts[:2]).upper()
        return self.email[:2].upper()

    @property
    def avatar_url(self):
        if self.avatar:
            try:
                return self.avatar.url
            except ValueError:
                return ""
        return ""

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def unread_notifications(self):
        return self.notifications.filter(is_read=False).count()

    def mark_email_verified(self):
        self.is_email_verified = True
        self.email_verified_at = timezone.now()
        self.save(update_fields=["is_email_verified", "email_verified_at"])

    def get_absolute_url(self):
        return reverse("accounts:profile")


class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    date_of_birth = models.DateField(blank=True, null=True)
    marketing_opt_in = models.BooleanField(default=False)
    preferred_payment = models.CharField(max_length=30, blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.email}"


class Address(models.Model):
    class AddressType(models.TextChoices):
        SHIPPING = "shipping", "Shipping"
        BILLING = "billing", "Billing"
        BOTH = "both", "Shipping & Billing"

    PROVINCES = [
        ("koshi", "Koshi"),
        ("madhesh", "Madhesh"),
        ("bagmati", "Bagmati"),
        ("gandaki", "Gandaki"),
        ("lumbini", "Lumbini"),
        ("karnali", "Karnali"),
        ("sudurpaschim", "Sudurpaschim"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=40, default="Home")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    alternate_phone = models.CharField(max_length=20, blank=True)
    street_address = models.CharField(max_length=255, help_text="Street, house number, apartment")
    landmark = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=80)
    district = models.CharField(max_length=80)
    province = models.CharField(max_length=30, choices=PROVINCES, default="bagmati")
    postal_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=50, default="Nepal")
    address_type = models.CharField(max_length=20, choices=AddressType.choices, default=AddressType.BOTH)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at"]
        indexes = [models.Index(fields=["user", "is_default"])]

    def __str__(self):
        return f"{self.full_name}, {self.city} ({self.label})"

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        elif not Address.objects.filter(user=self.user).exclude(pk=self.pk).exists():
            self.is_default = True
        super().save(*args, **kwargs)

    @property
    def single_line(self):
        parts = [self.street_address, self.city, self.district, self.province.title()]
        return ", ".join(p for p in parts if p)


class EmailOTP(models.Model):
    """A short-lived, hashed verification code sent to the account email."""

    MAX_ATTEMPTS = 5

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_otps")
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "email verification code"
        verbose_name_plural = "email verification codes"

    def __str__(self):
        return f"Code for {self.user.email}"

    @property
    def is_valid(self):
        return (
            self.used_at is None
            and self.attempts < self.MAX_ATTEMPTS
            and timezone.now() < self.expires_at
        )

    def matches(self, code: str) -> bool:
        return check_password(code, self.code_hash)

    def register_failed_attempt(self):
        self.attempts += 1
        self.save(update_fields=["attempts"])

    def consume(self):
        self.used_at = timezone.now()
        self.attempts += 1
        self.save(update_fields=["used_at", "attempts"])


class Notification(models.Model):
    class Kind(models.TextChoices):
        ORDER = "order", "Order"
        PAYMENT = "payment", "Payment"
        WISHLIST = "wishlist", "Wishlist"
        ACCOUNT = "account", "Account"
        PROMO = "promo", "Promotion"
        SYSTEM = "system", "System"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=140)
    message = models.CharField(max_length=400)
    url = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SYSTEM)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.user.email}: {self.title}"

    @classmethod
    def push(cls, user, title, message, url="", kind=Kind.SYSTEM):
        return cls.objects.create(user=user, title=title, message=message, url=url, kind=kind)
