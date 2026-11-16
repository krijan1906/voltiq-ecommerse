"""Email verification tokens and mailers."""
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import EmailVerificationToken, User


def issue_verification(user):
    EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).delete()
    token = secrets.token_urlsafe(32)
    record = EmailVerificationToken.objects.create(
        user=user, token=token, expires_at=timezone.now() + timedelta(days=3)
    )
    return record


def verification_url(token, request=None):
    path = reverse("accounts:verify_email", kwargs={"token": token})
    if request is not None:
        return request.build_absolute_uri(path)
    return f"{settings.SITE_URL}{path}"


def send_verification_email(user, token, request=None):
    url = verification_url(token, request)
    context = {"user": user, "url": url, "site_name": settings.SITE_NAME}
    text = render_to_string("emails/verify_email.txt", context)
    html = render_to_string("emails/verify_email.html", context)
    from django.core.mail import EmailMultiAlternatives

    email = EmailMultiAlternatives(
        f"Verify your {settings.SITE_NAME} account",
        text,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    email.attach_alternative(html, "text/html")
    email.send(fail_silently=True)
    return url


def notify_welcome(user):
    from apps.accounts.models import Notification

    Notification.push(
        user,
        f"Welcome to {settings.SITE_NAME}",
        "Your account is ready. Explore the latest laptops, phones and gaming gear.",
        url=reverse("core:home"),
        kind=Notification.Kind.ACCOUNT,
    )
