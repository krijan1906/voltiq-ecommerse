import base64
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.orders.models import Order
from apps.payments.gateways.base import VerificationResult
from apps.payments.models import Payment
from apps.payments.services import simulate_payment, verify_payment

logger = logging.getLogger("apps.payments")


def _payment_from_esewa_data(params):
    data = params.get("data")
    if not data:
        return None
    try:
        payload = json.loads(base64.b64decode(data).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    ref = payload.get("transaction_uuid")
    if not ref:
        return None
    return Payment.objects.filter(transaction_ref=ref, gateway=Payment.Gateway.ESEWA).select_related("order").first()


def _fallback_payment(order_number, gateway):
    if not order_number:
        return None
    return (
        Payment.objects.filter(order__order_number=order_number, gateway=gateway)
        .select_related("order")
        .order_by("-initiated_at")
        .first()
    )


@require_GET
def esewa_callback(request):
    order_number = request.GET.get("order", "")
    payment = _payment_from_esewa_data(request.GET) or _fallback_payment(order_number, Payment.Gateway.ESEWA)
    if not payment:
        messages.error(request, "We couldn't match this eSewa response to an order.")
        return render(request, "payments/failure.html", {"order": None, "payment": None, "reason": "Unknown transaction."})

    order = payment.order
    if not request.GET.get("data"):
        messages.warning(request, "The eSewa payment was cancelled or no response data was received.")
        return render(
            request,
            "payments/failure.html",
            {"order": order, "payment": payment, "reason": "Payment was cancelled or incomplete."},
        )

    result = verify_payment(payment, request.GET, request)
    if result.success:
        messages.success(
            request,
            f"Payment successful. Order {order.order_number} is confirmed — thank you!",
        )
        return redirect("orders:confirmation", order_number=order.order_number)
    messages.error(request, result.message or "We could not verify your eSewa payment.")
    return render(
        request,
        "payments/failure.html",
        {"order": order, "payment": payment, "reason": result.message},
    )


@require_GET
def khalti_callback(request):
    params = request.GET
    pidx = params.get("pidx", "")
    order_number = params.get("order", "") or params.get("purchase_order_id", "")
    payment = None
    if pidx:
        payment = (
            Payment.objects.filter(gateway=Payment.Gateway.KHALTI, gateway_ref=pidx)
            .select_related("order")
            .order_by("-initiated_at")
            .first()
        )
    if not payment:
        payment = _fallback_payment(order_number, Payment.Gateway.KHALTI)
    if not payment:
        messages.error(request, "We couldn't match this Khalti response to an order.")
        return render(request, "payments/failure.html", {"order": None, "payment": None, "reason": "Unknown transaction."})

    order = payment.order
    gateway_status = (params.get("status") or "").lower()
    if gateway_status and gateway_status not in {"completed", "pending", "initiated"}:
        payment.mark_failed(f"Khalti reported: {params.get('status')}")
        messages.error(request, "The Khalti payment was cancelled or failed. You can retry.")
        return render(
            request,
            "payments/failure.html",
            {"order": order, "payment": payment, "reason": f"Khalti reported: {params.get('status')}"},
        )

    result = verify_payment(payment, params, request)
    if result.success:
        messages.success(
            request,
            f"Payment successful. Order {order.order_number} is confirmed — thank you!",
        )
        return redirect("orders:confirmation", order_number=order.order_number)
    messages.error(request, result.message or "We could not verify your Khalti payment.")
    return render(
        request,
        "payments/failure.html",
        {"order": order, "payment": payment, "reason": result.message},
    )


@login_required
@require_http_methods(["GET", "POST"])
def simulate(request, transaction_ref):
    if not settings.PAYMENT_SIMULATION:
        raise Http404()
    payment = get_object_or_404(
        Payment.objects.select_related("order"), transaction_ref=transaction_ref, order__user=request.user
    )
    if payment.status == Payment.Status.SUCCESS:
        messages.info(request, "This payment is already complete.")
        return redirect("orders:confirmation", order_number=payment.order.order_number)
    if request.method == "POST":
        outcome = request.POST.get("outcome") == "success"
        result = simulate_payment(payment, outcome, request)
        if result.success:
            messages.success(request, "Simulated payment successful. Order confirmed.")
            return redirect("orders:confirmation", order_number=payment.order.order_number)
        messages.error(request, "Simulated payment failure recorded. You can retry payment.")
        return redirect("orders:payment", order_number=payment.order.order_number)
    return render(request, "payments/simulate.html", {"payment": payment, "order": payment.order})


@login_required
def failure(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    payment = order.payments.order_by("-initiated_at").first()
    reason = request.GET.get("reason") or (payment.failed_reason if payment else "")
    return render(request, "payments/failure.html", {"order": order, "payment": payment, "reason": reason})


@login_required
def bank_instructions(request, transaction_ref):
    payment = get_object_or_404(
        Payment.objects.select_related("order"), transaction_ref=transaction_ref, order__user=request.user
    )
    return render(request, "payments/bank.html", {"payment": payment, "order": payment.order})
