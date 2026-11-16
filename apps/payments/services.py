"""Payment orchestration: initiate, verify, simulate sandbox, refund."""
import logging
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order
from apps.payments.gateways import get_gateway
from apps.payments.gateways.base import PaymentGatewayError, PaymentInitiation, VerificationResult
from apps.payments.models import Payment, PaymentTransaction
from apps.payments.utils import client_ip

logger = logging.getLogger("apps.payments")


def _log(payment, event, message="", status="", request=None, request_data=None, response_data=None):
    return PaymentTransaction.objects.create(
        payment=payment,
        event=event,
        status=status,
        message=message[:300],
        request_data=request_data or {},
        response_data=response_data or {},
        ip_address=client_ip(request) if request else None,
    )


def available_payment_methods():
    methods = []
    for code in ("esewa", "khalti"):
        gateway = get_gateway(code)
        if gateway.is_configured:
            methods.append(gateway)
        elif settings.PAYMENT_SIMULATION:
            methods.append(gateway)
    methods.extend([get_gateway("cod"), get_gateway("bank")])
    return methods


@transaction.atomic
def start_payment(order, gateway_code, request):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.payment_status == Order.PaymentStatus.PAID:
        return None, PaymentInitiation(
            redirect_url=request.build_absolute_uri(
                reverse("orders:confirmation", kwargs={"order_number": order.order_number})
            ),
            message="This order is already paid.",
        )
    if not order.can_pay:
        raise PaymentGatewayError("This order can no longer be paid online.")

    gateway = get_gateway(gateway_code)
    if not gateway:
        raise PaymentGatewayError("Unknown payment method.")
    if gateway.is_online and not gateway.is_configured and not settings.PAYMENT_SIMULATION:
        raise PaymentGatewayError(f"{gateway.display_name} is not available right now.")

    for stale in order.payments.filter(status__in=[Payment.Status.INITIATED, Payment.Status.PENDING]):
        stale.mark_failed("Superseded by a new payment attempt.", status=Payment.Status.EXPIRED)

    attempt_number = order.payments.count() + 1
    payment = Payment.objects.create(
        order=order,
        gateway=gateway.code,
        amount=order.total,
        status=Payment.Status.INITIATED,
        attempt_number=attempt_number,
    )
    _log(payment, PaymentTransaction.Event.INITIATED, f"{gateway.display_name} attempt #{attempt_number}", request=request)

    # Sandbox simulator for local development when real credentials are absent.
    if gateway.is_online and not gateway.is_configured and settings.PAYMENT_SIMULATION:
        payment.status = Payment.Status.PENDING
        payment.gateway_ref = "SIMULATED"
        payment.gateway_payload = {"simulated": True}
        payment.save(update_fields=["status", "gateway_ref", "gateway_payload", "updated_at"])
        _log(
            payment,
            PaymentTransaction.Event.NOTE,
            "Development simulator used — no real gateway contacted.",
            status="simulated",
            request=request,
        )
        return payment, PaymentInitiation(
            redirect_url=request.build_absolute_uri(
                reverse("payments:simulate", kwargs={"transaction_ref": payment.transaction_ref})
            ),
            message="Sandbox simulator",
        )

    try:
        initiation = gateway.initiate(payment, order, request)
    except PaymentGatewayError as exc:
        payment.mark_failed(str(exc))
        _log(payment, PaymentTransaction.Event.FAILED, str(exc), status="failed", request=request)
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected gateway initiation error")
        payment.mark_failed("Payment gateway error. Please try again.")
        _log(payment, PaymentTransaction.Event.FAILED, str(exc), status="failed", request=request)
        raise PaymentGatewayError("Payment gateway error. Please try again.") from exc

    payment.status = Payment.Status.PENDING
    if initiation.form_fields:
        safe_payload = {k: v for k, v in initiation.form_fields.items() if k != "signature"}
        payment.gateway_payload = safe_payload
    payment.save(update_fields=["status", "gateway_payload", "updated_at"])
    order.payment_status = Order.PaymentStatus.PENDING
    order.save(update_fields=["payment_status", "updated_at"])
    _log(
        payment,
        PaymentTransaction.Event.NOTE,
        initiation.message or "Redirecting to gateway.",
        status="pending",
        request=request,
    )
    return payment, initiation


@transaction.atomic
def verify_payment(payment, params, request):
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    if payment.status == Payment.Status.SUCCESS:
        return VerificationResult(True, "Payment was already verified.", gateway_ref=payment.gateway_ref)
    if payment.order.payment_status == Order.PaymentStatus.PAID:
        return VerificationResult(False, "This order has already been paid.", gateway_ref=payment.gateway_ref)

    gateway = get_gateway(payment.gateway)
    _log(
        payment,
        PaymentTransaction.Event.CALLBACK,
        "Gateway callback received.",
        status="received",
        request=request,
        request_data={k: str(v)[:500] for k, v in params.items()},
    )
    if not gateway:
        return VerificationResult(False, "Unknown payment gateway.")

    try:
        result = gateway.verify(payment, params, request)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Payment verification crashed")
        result = VerificationResult(False, "Payment verification failed. Please retry.")

    _log(
        payment,
        PaymentTransaction.Event.VERIFIED if result.success else PaymentTransaction.Event.FAILED,
        result.message,
        status="success" if result.success else "failed",
        request=request,
        response_data=result.payload,
    )
    if result.success:
        try:
            payment.mark_success(payload=result.payload, gateway_ref=result.gateway_ref)
        except IntegrityError:
            logger.warning("Duplicate successful payment prevented for order %s", payment.order_id)
            return VerificationResult(
                False, "A payment has already been recorded for this order.", gateway_ref=payment.gateway_ref
            )
        _log(
            payment,
            PaymentTransaction.Event.SUCCEEDED,
            "Payment verified and order updated.",
            status="success",
            request=request,
        )
    else:
        if result.definitive:
            payment.mark_failed(result.message, payload=result.payload)
    return result


@transaction.atomic
def simulate_payment(payment, success, request):
    if not settings.PAYMENT_SIMULATION or not settings.DEBUG:
        raise PaymentGatewayError("Simulator is disabled.")
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    if payment.status == Payment.Status.SUCCESS:
        return VerificationResult(True, "Already paid.", gateway_ref=payment.gateway_ref)
    _log(
        payment,
        PaymentTransaction.Event.CALLBACK,
        "Development simulator callback.",
        status="simulated",
        request=request,
    )
    if success:
        payment.mark_success(
            payload={"simulated": True, "message": "Development simulator success"}, gateway_ref="SIMULATED"
        )
        _log(
            payment,
            PaymentTransaction.Event.SUCCEEDED,
            "Simulated payment marked successful.",
            status="success",
            request=request,
        )
        return VerificationResult(True, "Sandbox payment marked successful (simulated).", gateway_ref="SIMULATED")
    payment.mark_failed("Simulated payment failure.", payload={"simulated": True})
    return VerificationResult(False, "Sandbox payment marked as failed (simulated).")


@transaction.atomic
def mark_cod_collected(order, collected_by=None, note="Cash collected on delivery"):
    payment = order.payments.filter(gateway=Payment.Gateway.COD).order_by("-id").first()
    if not payment:
        payment = Payment.objects.create(
            order=order,
            gateway=Payment.Gateway.COD,
            amount=order.total,
            status=Payment.Status.PENDING,
            attempt_number=order.payments.count() + 1,
        )
    if payment.status != Payment.Status.SUCCESS:
        payment.mark_success(
            payload={"collected_by": collected_by.email if collected_by else "system", "note": note},
            gateway_ref="COD",
        )
        _log(payment, PaymentTransaction.Event.SUCCEEDED, note, status="success")
    order.payment_status = Order.PaymentStatus.PAID
    order.save(update_fields=["payment_status", "updated_at"])
    return payment


@transaction.atomic
def record_manual_refund(order, by=None, reason="Refund processed by staff"):
    payment = order.payments.filter(status=Payment.Status.SUCCESS).order_by("-id").first()
    if payment:
        payment.status = Payment.Status.REFUNDED
        payment.refunded_at = timezone.now()
        payment.save(update_fields=["status", "refunded_at", "updated_at"])
        _log(payment, PaymentTransaction.Event.REFUNDED, reason, status="refunded")
    order.payment_status = Order.PaymentStatus.REFUNDED
    order.status = Order.Status.REFUNDED
    order.save(update_fields=["payment_status", "status", "updated_at"])
    return payment
