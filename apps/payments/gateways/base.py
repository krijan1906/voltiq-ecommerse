from dataclasses import dataclass, field


class PaymentGatewayError(Exception):
    pass


@dataclass
class PaymentInitiation:
    """Result of starting a payment: either a redirect or an auto-submitted form."""

    redirect_url: str = ""
    form_url: str = ""
    form_fields: dict = field(default_factory=dict)
    message: str = ""

    @property
    def is_form(self):
        return bool(self.form_url and self.form_fields)


@dataclass
class VerificationResult:
    success: bool
    message: str = ""
    gateway_ref: str = ""
    payload: dict = field(default_factory=dict)
    definitive: bool = True


class BaseGateway:
    code = ""
    display_name = ""
    description = ""
    icon = "wallet"
    is_online = True

    @property
    def is_configured(self):
        return True

    def initiate(self, payment, order, request) -> PaymentInitiation:
        raise NotImplementedError

    def verify(self, payment, params, request) -> VerificationResult:
        raise PaymentGatewayError("This payment method cannot be verified online.")
