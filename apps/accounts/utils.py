"""Email verification codes and mailers.

Registration sends a four-digit code to the address on the account. The code
is stored only as a password hash, expires after ten minutes and is invalidated
after five failed attempts. No verification link is emailed any more.
"""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import EmailOTP

logger = logging.getLogger(__name__)

OTP_LENGTH = 4
OTP_TTL_MINUTES = 10
OTP_RESEND_SECONDS = 60


def generate_otp() -> str:
    """Return a cryptographically random numeric code, zero padded."""
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def active_otp(user):
    """The newest usable code for this user, or None."""
    return (
        EmailOTP.objects.filter(user=user, used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )


def issue_otp(user):
    """Create a fresh code for the user, replacing any previous one."""
    EmailOTP.objects.filter(user=user, used_at__isnull=True).delete()
    code = generate_otp()
    record = EmailOTP.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    return record, code


def resend_ready_in(user) -> int:
    """Seconds the user must wait before another code can be requested."""
    record = active_otp(user)
    if not record:
        return 0
    elapsed = (timezone.now() - record.created_at).total_seconds()
    return max(0, int(OTP_RESEND_SECONDS - elapsed))


def send_otp_email(user, code: str) -> None:
    context = {
        "user": user,
        "code": code,
        "site_name": settings.SITE_NAME,
        "expires_minutes": OTP_TTL_MINUTES,
    }
    text = render_to_string("emails/verify_otp.txt", context)
    html = render_to_string("emails/verify_otp.html", context)
    email = EmailMultiAlternatives(
        f"{code} is your {settings.SITE_NAME} verification code",
        text,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    email.attach_alternative(html, "text/html")
    try:
        email.send(fail_silently=False)
    except Exception:
        # Registration must not fail because the mail server is unreachable,
        # but the operator needs to see the problem in the log.
        logger.exception("Could not send verification code to %s", user.email)


def notify_welcome(user):
    from apps.accounts.models import Notification

    Notification.push(
        user,
        f"Welcome to {settings.SITE_NAME}",
        "Your account is ready. Explore the latest laptops, phones and gaming gear.",
        url=reverse("core:home"),
        kind=Notification.Kind.ACCOUNT,
    )
