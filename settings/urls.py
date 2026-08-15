from django.urls import path

from settings.views import PaymentMethodUpdateView, SubscriptionCancelView, SubscriptionView

urlpatterns = [
    path("subscription/", SubscriptionView.as_view(), name="subscription-detail"),
    path("subscription/payment-method/", PaymentMethodUpdateView.as_view(), name="payment-method-update"),
    path("subscription/cancel/", SubscriptionCancelView.as_view(), name="subscription-cancel"),
]