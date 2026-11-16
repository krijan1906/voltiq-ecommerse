"""Payment attempts plus an immutable audit trail of gateway interactions.

No card numbers, CVVs or gateway secrets are ever persisted. Only gateway
references and non-sensitive response payloads are stored.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.orders.models import Order


class Payment(models.Model):
    class Gateway(models.TextChoices):
        ESEWA = "esewa", "eSewa"
        KHALTI = "khalti", "Khalti"
        COD = "cod", "Cash on Delivery"
        BANK = "bank", "Bank Transfer"
        STRIPE = "stripe", "Stripe"

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    gateway = models.CharField(max_length=20, choices=Gateway.choices, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="NPR")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED, db_index=True)
    transaction_ref = models.CharField(max_length=64, unique=True, default=uuid.uuid4, editable=False)
    gateway_ref = models.CharField(max_length=160, blank=True, db_index=True)
    gateway_payload = models.JSONField(default=dict, blank=True)
    verification_payload = models.JSONField(default=dict, blank=True)
    is_verified = models.BooleanField(default=False)
    attempt_number = models.PositiveSmallIntegerField(default=1)
    initiated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    failed_reason = models.CharField(max_length=300, blank=True)
    refunded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-initiated_at"]
        indexes = [
            models.Index(fields=["order", "-initiated_at"]),
            models.Index(fields=["gateway", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["order"], condition=models.Q(status="success"), name="one_successful_payment_per_order"
            )
        ]

    def __str__(self):
        return f"{self.get_gateway_display()} {self.transaction_ref[:10]} ({self.status})"

    @property
    def is_success(self):
        return self.status == self.Status.SUCCESS

    @property
    def is_expired(self):
        timeout = getattr(settings, "PAYMENT_TIMEOUT_MINUTES", 30)
        return self.status in {self.Status.INITIATED, self.Status.PENDING} and (
            timezone.now() - self.initiated_at
        ).total_seconds() > timeout * 60

    def mark_success(self, payload=None, gateway_ref=""):
        if self.status == self.Status.SUCCESS:
            return False
        self.status = self.Status.SUCCESS
        self.is_verified = True
        self.completed_at = timezone.now()
        self.verification_payload = payload or {}
        if gateway_ref:
            self.gateway_ref = gateway_ref
        self.save()
        order = self.order
        order.payment_status = Order.PaymentStatus.PAID
        if order.status == Order.Status.PENDING:
            order.status = Order.Status.CONFIRMED
            order.confirmed_at = timezone.now()
        order.save(update_fields=["payment_status", "status", "confirmed_at", "updated_at"])
        if order.user_id:
            from apps.accounts.models import Notification

            Notification.push(
                order.user,
                "Payment successful",
                f"We received your payment for order {order.order_number}.",
                url=order.get_absolute_url(),
                kind=Notification.Kind.PAYMENT,
            )
        return True

    def mark_failed(self, reason="", status=None, payload=None):
        if self.status in {
            self.Status.SUCCESS,
            self.Status.FAILED,
            self.Status.CANCELLED,
            self.Status.EXPIRED,
            self.Status.REFUNDED,
        }:
            return False
        self.status = status or self.Status.FAILED
        self.failed_reason = reason[:300]
        self.completed_at = timezone.now()
        if payload:
            self.verification_payload = payload
        self.save()
        order = self.order
        if order.payment_status != Order.PaymentStatus.PAID:
            order.payment_status = Order.PaymentStatus.FAILED
            order.save(update_fields=["payment_status", "updated_at"])
        return True


class PaymentTransaction(models.Model):
    class Event(models.TextChoices):
        INITIATED = "initiated", "Initiation"
        CALLBACK = "callback", "Callback received"
        VERIFIED = "verified", "Server-side verification"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"
        NOTE = "note", "Note"

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="transactions")
    event = models.CharField(max_length=20, choices=Event.choices)
    status = models.CharField(max_length=30, blank=True)
    message = models.CharField(max_length=300, blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.payment.transaction_ref[:10]} — {self.get_event_display()}"
