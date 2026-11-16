"""Khalti ePayment v2 integration (sandbox + production via env)."""
import logging
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.urls import reverse

from apps.payments.gateways.base import (
    BaseGateway,
    PaymentGatewayError,
    PaymentInitiation,
    VerificationResult,
)

logger = logging.getLogger("apps.payments")


class KhaltiGateway(BaseGateway):
    code = "khalti"
    display_name = "Khalti"
    description = "Pay with Khalti wallet, bank or connected wallet"
    icon = "khalti"

    @property
    def is_configured(self):
        return bool(settings.KHALTI_SECRET_KEY)

    @property
    def headers(self):
        return {"Authorization": f"key {settings.KHALTI_SECRET_KEY}"}

    def initiate(self, payment, order, request):
        if not self.is_configured:
            raise PaymentGatewayError("Khalti is not configured. Add your merchant key to .env.")

        return_url = request.build_absolute_uri(reverse("payments:khalti_callback"))
        return_url = f"{return_url}?order={order.order_number}"
        payload = {
            "return_url": return_url,
            "website_url": settings.KHALTI_WEBSITE_URL or request.build_absolute_uri("/"),
            "amount": int(payment.amount * 100),
            "purchase_order_id": order.order_number,
            "purchase_order_name": f"Voltiq order {order.order_number}",
            "customer_info": {
                "name": order.full_name,
                "email": order.email,
                "phone": order.phone,
            },
        }
        try:
            response = requests.post(
                settings.KHALTI_INIT_URL, json=payload, headers=self.headers, timeout=20
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.warning("Khalti initiation failed: %s", exc)
            raise PaymentGatewayError("Khalti could not be reached. Please try again or use another method.")
        except ValueError as exc:
            raise PaymentGatewayError("Khalti returned an invalid response.") from exc

        pidx = data.get("pidx")
        payment_url = data.get("payment_url")
        if not pidx or not payment_url:
            logger.warning("Khalti initiation response missing fields: %s", data)
            raise PaymentGatewayError("Khalti did not return a payment URL. Please try again.")

        payment.gateway_ref = pidx[:160]
        payment.gateway_payload = {"pidx": pidx}
        payment.save(update_fields=["gateway_ref", "gateway_payload", "updated_at"])
        return PaymentInitiation(redirect_url=payment_url, message="Redirecting you to Khalti…")

    def verify(self, payment, params, request):
        pidx = params.get("pidx") or payment.gateway_ref
        if not pidx:
            return VerificationResult(False, "Missing Khalti pidx.", definitive=False)
        try:
            response = requests.post(
                settings.KHALTI_LOOKUP_URL,
                json={"pidx": pidx},
                headers=self.headers,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Khalti lookup failed: %s", exc)
            return VerificationResult(
                False, "We could not verify this payment with Khalti. Please retry.", definitive=False
            )

        if data.get("status") != "Completed":
            return VerificationResult(False, f"Khalti payment is {data.get('status', 'not completed')}.", payload=data)
        if data.get("purchase_order_id") != payment.order.order_number:
            return VerificationResult(False, "Order reference mismatch.", payload=data)
        if data.get("pidx") not in {None, pidx}:
            return VerificationResult(False, "Payment identifier mismatch.", payload=data)
        try:
            verified_paisa = Decimal(str(data.get("total_amount", "0")))
        except InvalidOperation:
            verified_paisa = Decimal("0")
        if verified_paisa != payment.amount * 100:
            return VerificationResult(False, "Paid amount does not match the order total.", payload=data)

        return VerificationResult(
            True,
            "Khalti payment verified.",
            gateway_ref=data.get("transaction_id", pidx),
            payload=data,
        )
