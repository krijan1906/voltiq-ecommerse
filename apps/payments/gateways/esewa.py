"""eSewa ePay v2 integration (sandbox + production endpoints via env)."""
import base64
import json
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.urls import reverse

from apps.payments.gateways.base import (
    BaseGateway,
    PaymentGatewayError,
    PaymentInitiation,
    VerificationResult,
)
from apps.payments.utils import hmac_sha256_base64, safe_compare

logger = logging.getLogger("apps.payments")


class EsewaGateway(BaseGateway):
    code = "esewa"
    display_name = "eSewa"
    description = "Pay securely with your eSewa wallet"
    icon = "esewa"

    @property
    def is_configured(self):
        return bool(settings.ESEWA_SECRET_KEY and settings.ESEWA_PRODUCT_CODE)

    def _callback_url(self, request, name, order):
        url = request.build_absolute_uri(reverse(name))
        return f"{url}?order={order.order_number}"

    def initiate(self, payment, order, request):
        if not self.is_configured:
            raise PaymentGatewayError("eSewa is not configured. Add sandbox credentials to .env.")

        total = f"{payment.amount:.2f}"
        signed_field_names = "total_amount,transaction_uuid,product_code"
        message = (
            f"total_amount={total},transaction_uuid={payment.transaction_ref},"
            f"product_code={settings.ESEWA_PRODUCT_CODE}"
        )
        signature = hmac_sha256_base64(settings.ESEWA_SECRET_KEY, message)
        fields = {
            "amount": total,
            "tax_amount": "0",
            "total_amount": total,
            "transaction_uuid": payment.transaction_ref,
            "product_code": settings.ESEWA_PRODUCT_CODE,
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "success_url": self._callback_url(request, "payments:esewa_callback", order),
            "failure_url": self._callback_url(request, "payments:esewa_callback", order),
            "signed_field_names": signed_field_names,
            "signature": signature,
        }
        payment.gateway_ref = payment.transaction_ref
        payment.save(update_fields=["gateway_ref", "updated_at"])
        return PaymentInitiation(
            form_url=settings.ESEWA_INIT_URL,
            form_fields=fields,
            message="Redirecting you to eSewa…",
        )

    def verify(self, payment, params, request):
        data_param = params.get("data")
        if not data_param:
            return VerificationResult(False, "Missing eSewa response data.", definitive=False)
        try:
            payload = json.loads(base64.b64decode(data_param).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return VerificationResult(False, "Invalid eSewa response encoding.", definitive=False)

        if payload.get("status") != "COMPLETE":
            return VerificationResult(False, f"eSewa returned status {payload.get('status', 'UNKNOWN')}.", payload=payload)
        if payload.get("transaction_uuid") != payment.transaction_ref:
            return VerificationResult(False, "Transaction reference mismatch.", payload=payload)

        signed_fields = (payload.get("signed_field_names") or "").split(",")
        if not signed_fields or not payload.get("signature"):
            return VerificationResult(False, "eSewa signature is missing.", payload=payload, definitive=False)
        message = ",".join(f"{field}={payload.get(field, '')}" for field in signed_fields)
        expected = hmac_sha256_base64(settings.ESEWA_SECRET_KEY, message)
        if not safe_compare(expected, payload.get("signature", "")):
            return VerificationResult(False, "eSewa signature verification failed.", payload=payload, definitive=False)

        try:
            response = requests.get(
                settings.ESEWA_STATUS_URL,
                params={
                    "product_code": settings.ESEWA_PRODUCT_CODE,
                    "total_amount": f"{payment.amount:.2f}",
                    "transaction_uuid": payment.transaction_ref,
                },
                timeout=15,
            )
            response.raise_for_status()
            status_data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("eSewa status verification failed: %s", exc)
            return VerificationResult(
                False,
                "We could not verify the payment with eSewa. If you were charged, please retry verification.",
                payload=payload,
                definitive=False,
            )

        if status_data.get("status") != "COMPLETE":
            return VerificationResult(
                False, f"eSewa payment is {status_data.get('status', 'not complete')}.", payload=status_data
            )
        try:
            verified_amount = Decimal(str(status_data.get("total_amount", "0")))
        except InvalidOperation:
            verified_amount = Decimal("0")
        if verified_amount != payment.amount:
            return VerificationResult(False, "Paid amount does not match the order total.", payload=status_data)
        if status_data.get("transaction_uuid") and status_data["transaction_uuid"] != payment.transaction_ref:
            return VerificationResult(False, "Verified transaction does not match.", payload=status_data)

        return VerificationResult(
            True,
            "eSewa payment verified.",
            gateway_ref=payload.get("transaction_code") or status_data.get("ref_id", ""),
            payload={"callback": payload, "status_check": status_data},
        )
