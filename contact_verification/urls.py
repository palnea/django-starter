from django.urls import path

from contact_verification.views import (
    ContactVerificationViewSet,
    CodeVerificationViewSet,
)

app_name = "contact_verification"

contact_verification = ContactVerificationViewSet.as_view({"post": "create"})
verify_contact = ContactVerificationViewSet.as_view({"post": "verify"})
email_verification = CodeVerificationViewSet.as_view({"post": "verify_email"})
phone_verification = CodeVerificationViewSet.as_view({"post": "verify_phone"})


urlpatterns = [
    path("send-the-code/", contact_verification, name="contact-verification"),
    path("verify-the-code/", verify_contact, name="verify-contact"),
    path("verify-email/", email_verification, name="email-verification"),
    path("verify-phone/", phone_verification, name="phone-verification"),
]
