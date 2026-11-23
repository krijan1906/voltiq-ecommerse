from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.forms import (
    AddressForm,
    LoginForm,
    OTPForm,
    ProfileForm,
    RegisterForm,
    StyledPasswordChangeForm,
    StyledSetPasswordForm,
)
from apps.accounts.models import Address, Notification
from apps.accounts.utils import (
    OTP_TTL_MINUTES,
    active_otp,
    issue_otp,
    notify_welcome,
    resend_ready_in,
    send_otp_email,
)
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.wishlist.models import Wishlist


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                _, code = issue_otp(user)
        except IntegrityError:
            # Two submissions can both pass the duplicate check before either
            # row is written (for example a double-clicked submit button).
            # The unique constraint is the final authority; report it in the
            # form instead of returning a 500 page.
            form.add_error("email", "An account with this email already exists. Try signing in.")
        else:
            send_otp_email(user, code)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            notify_welcome(user)
            messages.success(
                request,
                f"Welcome to {settings.SITE_NAME}! Enter the 4-digit code we emailed to {user.email}.",
            )
            request.session["pending_verification"] = True
            return redirect("accounts:verify_pending")
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        if not form.cleaned_data.get("remember_me"):
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        messages.success(request, f"Welcome back, {user.get_short_name()}.")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("accounts:dashboard")
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been signed out securely.")
    return redirect("core:home")


@login_required
def verify_pending(request):
    if request.user.is_email_verified:
        messages.success(request, "Your email is already verified.")
        return redirect("accounts:dashboard")
    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = active_otp(request.user)
        if record is None or not record.is_valid:
            form.add_error("code", "That code is no longer valid. Request a new one.")
        elif not record.matches(form.cleaned_data["code"]):
            record.register_failed_attempt()
            remaining = max(0, record.MAX_ATTEMPTS - record.attempts)
            if remaining:
                form.add_error(
                    "code",
                    f"That code is not correct. {remaining} attempt{'s' if remaining > 1 else ''} left.",
                )
            else:
                form.add_error("code", "Too many incorrect attempts. Request a new code.")
        else:
            record.consume()
            request.user.mark_email_verified()
            notify_welcome(request.user)
            request.session.pop("pending_verification", None)
            messages.success(request, "Email verified! You can now complete checkout.")
            return redirect("accounts:dashboard")
    return render(
        request,
        "accounts/verify_pending.html",
        {
            "form": form,
            "email": request.user.email,
            "resend_wait": resend_ready_in(request.user),
            "expires_minutes": OTP_TTL_MINUTES,
        },
    )


@login_required
@ratelimit(key="user", rate="5/h", method="POST", block=True)
def resend_verification(request):
    if request.user.is_email_verified:
        messages.info(request, "Your email is already verified.")
        return redirect("accounts:dashboard")
    wait = resend_ready_in(request.user)
    if wait:
        messages.warning(request, f"Please wait {wait} seconds before requesting another code.")
        return redirect("accounts:verify_pending")
    _, code = issue_otp(request.user)
    send_otp_email(request.user, code)
    messages.success(request, f"A new 4-digit code was sent to {request.user.email}.")
    return redirect("accounts:verify_pending")


@login_required
def dashboard(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items").order_by("-created_at")
    paid_total = orders.filter(payment_status=Order.PaymentStatus.PAID).aggregate(total=Sum("total"))["total"] or 0
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    context = {
        "recent_orders": orders[:5],
        "order_count": orders.count(),
        "paid_total": paid_total,
        "addresses": request.user.addresses.all()[:3],
        "wishlist_count": wishlist.item_count,
        "pending_payments": orders.filter(payment_status=Order.PaymentStatus.PENDING).count(),
        "notifications": request.user.notifications.all()[:5],
    }
    return render(request, "accounts/dashboard.html", context)


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def address_list(request):
    addresses = request.user.addresses.all()
    return render(request, "accounts/addresses.html", {"addresses": addresses})


@login_required
def address_create(request):
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    form = AddressForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        address = form.save()
        messages.success(request, "Delivery address saved.")
        if next_url:
            return redirect(next_url)
        return redirect("accounts:addresses")
    return render(request, "accounts/address_form.html", {"form": form, "title": "Add a new address", "next": next_url})


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    form = AddressForm(request.POST or None, instance=address, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Address updated.")
        return redirect("accounts:addresses")
    return render(
        request, "accounts/address_form.html", {"form": form, "title": "Edit address", "address": address}
    )


@login_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    if not request.user.addresses.filter(is_default=True).exists():
        first = request.user.addresses.first()
        if first:
            first.is_default = True
            first.save(update_fields=["is_default"])
    messages.success(request, "Address removed.")
    return redirect("accounts:addresses")


@login_required
@require_POST
def address_set_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save(update_fields=["is_default"])
    messages.success(request, "Default address updated.")
    return redirect("accounts:addresses")


@login_required
def notifications(request):
    items = request.user.notifications.all()
    if request.GET.get("filter") == "unread":
        items = items.filter(is_read=False)
    return render(request, "accounts/notifications.html", {"notifications": items})


@login_required
@require_POST
def notifications_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("accounts:notifications")


@login_required
def payment_history(request):
    payments = (
        Payment.objects.filter(order__user=request.user)
        .select_related("order")
        .order_by("-initiated_at")
    )
    return render(request, "accounts/payments.html", {"payments": payments})


class AccountPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, form.user)
        messages.success(self.request, "Password changed successfully.")
        return response


class AccountPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "emails/password_reset.txt"
    html_email_template_name = "emails/password_reset.html"
    subject_template_name = "emails/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")
    from_email = settings.DEFAULT_FROM_EMAIL

    def form_valid(self, form):
        messages.info(self.request, "If that email exists, a reset link has been sent.")
        return super().form_valid(form)


class AccountPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class AccountPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class AccountPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
