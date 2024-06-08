import jwt
from django.test import override_settings
from django.urls import reverse
from mock import patch
from model_bakery import baker

from authy.models import Account
from contact_verification.models import ContactVerification
from custom_test.base_test import CustomIntegrationTestCase
from user.models import User


class AuthenticationTestCase(CustomIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.create_common_models()
        self.email_password = "123"
        self.email_account = baker.make(
            Account, id="381c8642-6135-4efe-a487-4b93a4217c06"
        )
        self.email_account.set_password(self.email_password)
        self.email_account.save()
        self.email_user = baker.make(
            User,
            id="381c8642-6135-4efe-a487-4b93a4217c06",
            account=self.email_account,
            email="myapp@yopmail.com",
        )

    @patch("communications.clients.sms.NetgsmSMSClient.send_sms")
    @patch("communications.clients.email.DjangoEmailClient.send_email")
    def test_registration_with_phone(self, mock_send_email, mock_send_sms):
        mock_send_email.return_value = True
        mock_send_sms.return_value = True

        id = "c392a9ca-2c4a-4c38-be8c-5225b758f0a9"
        code = "code"
        baker.make(ContactVerification, id=id, code=code)
        password = "password"
        confirm_password = "password"
        phone = "+905555555555"
        data = {
            "phone": phone,
            "password": password,
            "verify_password": confirm_password,
            "verification_id": id,
            "verification_code": code,
        }

        url = reverse("register")

        self.assertFalse(User.objects.filter(phone=phone).exists())

        response = self.client.post(url, data, format="json")

        self.assertTrue(User.objects.filter(phone=phone).exists())
        self.assertEqual(response.status_code, 200)

    @patch("communications.clients.sms.NetgsmSMSClient.send_sms")
    @patch("communications.clients.email.DjangoEmailClient.send_email")
    def test_registration_with_email(self, mock_send_email, mock_send_sms):
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        id = "c392a9ca-2c4a-4c38-be8c-5225b758f0a9"
        code = "code"
        baker.make(ContactVerification, id=id, code=code)
        password = "password"
        confirm_password = "password"
        email = "alper@yopmail.com"
        data = {
            "email": email,
            "password": password,
            "verify_password": confirm_password,
            "verification_id": id,
            "verification_code": code,
        }

        url = reverse("register")

        self.assertFalse(User.objects.filter(email=email).exists())

        response = self.client.post(url, data, format="json")

        self.assertTrue(User.objects.filter(email=email).exists())
        self.assertEqual(response.status_code, 200)

    def test_login_with_phone(self):
        data = {"phone": self.user.phone, "password": "123"}

        url = reverse("login")

        self.assertTrue(User.objects.filter(phone=self.user.phone).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        access_token = response.data["response_body"]["access"]

        response_phone = jwt.decode(
            access_token, options={"verify_signature": False}
        ).get("phone")
        self.assertEqual(response_phone, self.user.phone)

    def test_login_with_invalid_phone(self):
        data = {"phone": "+905553330000", "password": "123"}

        url = reverse("login")

        self.assertTrue(User.objects.filter(phone=self.user.phone).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 404)

    def test_login_with_email(self):
        data = {"email": self.email_user.email, "password": self.email_password}

        url = reverse("login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

        access_token = response.data["response_body"]["access"]

        response_email = jwt.decode(
            access_token, options={"verify_signature": False}
        ).get("email")
        self.assertEqual(response_email, self.email_user.email)

    def test_login_with_invalid_email(self):
        data = {"email": "invalidemail@email.com", "password": self.email_password}

        url = reverse("login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 404)

    def test_refresh_token(self):
        data = {"email": self.email_user.email, "password": self.email_password}

        url = reverse("login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        refresh_token = response.data["response_body"]["refresh"]

        data = {"refresh": refresh_token}
        url = reverse("token_refresh")
        refresh_response = self.client.post(url, data, format="json")
        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotEqual(refresh_response.data.get("access", None), None)

    def test_update_password(self):
        data = {"email": self.email_user.email}


class SocialAuthenticationTestCase(CustomIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.create_common_models()
        self.email_password = "123"
        self.email_account = baker.make(
            Account, id="381c8642-6135-4efe-a487-4b93a4217c06"
        )
        self.email_account.set_password(self.email_password)
        self.email_account.save()
        self.email_user = baker.make(
            User,
            id="381c8642-6135-4efe-a487-4b93a4217c06",
            account=self.email_account,
            email="myapp@yopmail.com"
        )

    @override_settings(GOOGLE_CLIENT_ID="google")
    @patch("authy.social_auth.google.Google.validate")
    def test_google_social_auth(self, mock_google_validate):
        mock_google_validate.return_value = {
            "sub": "abcdef",
            "aud": "",
            "email": self.email_user.email,
            "name": self.email_user.fullname
        }
        data = {"auth_token": "auth_token"}
        url = reverse("google_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

    @patch("authy.social_auth.facebook.Facebook.validate")
    def test_facebook_social_auth(self, mock_facebook_validate):
        mock_facebook_validate.return_value = {
            "id": "123456",
            "email": self.email_user.email,
            "name": self.email_user.fullname
        }
        data = {"auth_token": "auth_token"}
        url = reverse("facebook_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

    @patch("authy.social_auth.apple.Apple.validate")
    def test_apple_social_auth(self, mock_apple_validate):
        mock_apple_validate.return_value = {
            "email": self.email_user.email
        }
        data = {"auth_token": "auth_token", "code": "code"}
        url = reverse("apple_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
