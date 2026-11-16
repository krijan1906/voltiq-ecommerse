"""Cash on delivery and manual bank transfer gateways."""
from django.urls import reverse

from apps.payments.gateways.base import BaseGateway, PaymentInitiation


class CashOnDeliveryGateway(BaseGateway):
    code = "cod"
    display_name = "Cash on Delivery"
    description = "Pay in cash when your order arrives"
    icon = "cash"
    is_online = False

    def initiate(self, payment, order, request):
        return PaymentInitiation(
            redirect_url=request.build_absolute_uri(
                reverse("orders:confirmation", kwargs={"order_number": order.order_number})
            ),
            message="Your order is confirmed. Please keep the exact amount ready on delivery.",
        )


class BankTransferGateway(BaseGateway):
    code = "bank"
    display_name = "Bank Transfer"
    description = "Direct bank deposit or transfer — verified by our team"
    icon = "bank"
    is_online = False

    def initiate(self, payment, order, request):
        return PaymentInitiation(
            redirect_url=request.build_absolute_uri(
                reverse("payments:bank_instructions", kwargs={"transaction_ref": payment.transaction_ref})
            ),
            message="Complete your bank transfer using the reference shown.",
        )
