from django.test import override_settings
from django.urls import reverse
from mock import patch
from mock.mock import Mock

from communications.services import CommunicationMedium
from contact_verification.models import ContactVerification
from custom_test.base_test import CustomIntegrationTestCase


class ContactVerificationTestCase(CustomIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.create_common_models()

    @override_settings(SMS_HEADER="MyApp")
    @patch("communications.clients.sms.NetgsmSMSClient.send_sms")
    def test_contact_verification(self, m_sms_response):
        phone = "+905553330000"

        m_sms_response.return_value = Mock(text="0")

        data = {"phone": phone}

        url = reverse("contact-verification")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 201)

        id = response.data.get("response_body").get("id")
        contact_verification = ContactVerification.objects.get(id=id)
        self.assertIsNotNone(contact_verification)
        m_sms_response.assert_called_once_with(
            receiver=phone.replace("+", "00"),
            language="en",
            message=f"Verification code for MyApp: {contact_verification.code}",
            header="MyApp",
        )

    def test_contact_verification_verify(self):
        self.user.phone_verified = False
        self.user.save()
        contact_verification = ContactVerification.objects.create(
            medium=CommunicationMedium.PHONE.value,
            receiver_address=self.user.phone_as_international,
            code="123456",
        )

        data = {"uuid": contact_verification.id, "code": "123456"}

        url = reverse("verify-contact")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("response_code"), "MSG_GENERAL_SUCCESS")
        contact_verification.refresh_from_db()
        self.assertEqual(
            contact_verification.status, ContactVerification.Status.VERIFIED.value
        )

        # Check if user phone is verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.phone_verified)

    def test_verify_code_exceed_number_of_max_attempts(self):
        phone = "+905553330000"

        contact_verification = ContactVerification.objects.create(
            medium="phone", receiver_address=phone, code="123456"
        )

        false_code = "123457"
        data = {"uuid": contact_verification.id, "code": false_code}

        url = reverse("verify-contact")
        for i in range(3):
            response = self.client.post(url, data, format="json")

        contact_verification.refresh_from_db()
        self.assertEqual(
            ContactVerification.Status.FAILED.value, contact_verification.status
        )
        self.assertEqual(3, contact_verification.attempts)

        data["code"] = contact_verification.code
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get("response_code"), "ERR_GENERAL_VALIDATION_ERROR"
        )

    @patch("communications.clients.email.DjangoEmailClient.send_email")
    def test_contact_verification_email(self, m_send_email):
        email = "test@myapp.com"
        data = {"email": email}
        url = reverse("contact-verification")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ContactVerification.objects.filter(receiver_address=email).exists()
        )
        m_send_email.assert_called_once()

    def test_verify_code_email(self):
        email = "test@myapp.com"
        self.user.email = email
        self.user.email_verified = False
        self.user.save()
        contact_verification = ContactVerification.objects.create(
            medium=CommunicationMedium.EMAIL.value,
            receiver_address=email,
            code="123456",
        )
        code = "123456"
        data = {"uuid": contact_verification.id, "code": code}
        url = reverse("verify-contact")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("response_code"), "MSG_GENERAL_SUCCESS")
        contact_verification.refresh_from_db()
        self.assertEqual(
            contact_verification.status, ContactVerification.Status.VERIFIED.value
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertEqual(self.user.email, email)
