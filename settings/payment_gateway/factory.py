from django.conf import settings as django_settings

from settings.payment_gateway.mock import MockPaymentGateway
from settings.payment_gateway.real import RealPaymentGateway


def get_payment_gateway():
    mode = getattr(django_settings, "PAYMENT_GATEWAY_MODE", "mock")
    if mode == "mock":
        return MockPaymentGateway()
    return RealPaymentGateway()