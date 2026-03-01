from django.urls import path

from payment.views import (
    PaymentViewSet,
    BuyableViewSet,
    GooglePlayWebhookViewSet,
    AppStoreWebhookViewSet,
    QonversionWebhookViewSet,
)

payment_action_view_set = PaymentViewSet.as_view(
    {
        "post": "make_purchase",
    }
)

buyable_viewset = BuyableViewSet.as_view({"get": "list", "post": "create"})

buyable_detail_viewset = BuyableViewSet.as_view(
    {"put": "update", "patch": "partial_update", "get": "retrieve", "delete": "destroy"}
)

appstore_webhook_viewset = AppStoreWebhookViewSet.as_view({"post": "create"})

googleplay_webhook_viewset = GooglePlayWebhookViewSet.as_view({"post": "create"})

qonversion_webhook_viewset = QonversionWebhookViewSet.as_view({"post": "create"})

payment_qonversion_identify_viewset = PaymentViewSet.as_view(
    {"post": "qonversion_identify"}
)

urlpatterns = [
    path("verify_receipt/", payment_action_view_set, name="payment_action"),
    path("buyable/", buyable_viewset, name="buyable-viewset"),
    path("buyable/<int:id>/", buyable_detail_viewset, name="buyable-detail-viewset"),
    path(
        "appstore/webhook/", appstore_webhook_viewset, name="appstore-webhook-viewset"
    ),
    path(
        "googleplay/webhook/",
        googleplay_webhook_viewset,
        name="googleplay-webhook-viewset",
    ),
    path(
        "qonversion/webhook/",
        qonversion_webhook_viewset,
        name="qonversion-webhook-viewset",
    ),
    path(
        "qonversion/identify/",
        payment_qonversion_identify_viewset,
        name="qonversion-identify",
    ),
]
