from django.test import override_settings
from django.urls import reverse
from mock import patch
from mock.mock import Mock

from contact_verification.models import ContactVerification
from custom_test.base_test import CustomIntegrationTestCase


class ContactVerificationTestCase(CustomIntegrationTestCase):
    @override_settings(SMS_HEADER="MyApp")
    @patch("communications.clients.sms.NetgsmSMSClient.send_sms")
    def test_contact_verification(self, m_sms_response):
        phone = "+905553330000"

        m_sms_response.return_value = Mock(text="0")

        data = {"phone": phone}

        url = reverse("contact-verification")
        response = self.client.post(url, data, format="json")

        id = response.data["response_body"]["id"]

        self.assertEqual(response.status_code, 201)
        self.assertTrue(ContactVerification.objects.filter(pk=id).exists())
        m_sms_response.assert_called_once_with(
            receiver=phone.replace("+", "00"),
            language="en",
            message=f"Uygulama giriş kodu: {ContactVerification.objects.get(pk=id).code} Lütfen kimseyle paylaşmayınız.",
            header="MyApp",
        )
