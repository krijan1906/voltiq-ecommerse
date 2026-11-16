from apps.payments.gateways.cod import BankTransferGateway, CashOnDeliveryGateway
from apps.payments.gateways.esewa import EsewaGateway
from apps.payments.gateways.khalti import KhaltiGateway

GATEWAYS = {
    gateway.code: gateway
    for gateway in [EsewaGateway(), KhaltiGateway(), CashOnDeliveryGateway(), BankTransferGateway()]
}

ONLINE_GATEWAYS = [gateway for gateway in GATEWAYS.values() if gateway.is_online]


def get_gateway(code):
    return GATEWAYS.get((code or "").lower())
