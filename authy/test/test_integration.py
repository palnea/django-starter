import jwt
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from mock import patch
from model_bakery import baker

from authy.models import Account
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
            email_verified=True,
        )

    def test_admin_group_exists(self):
        """
        This test checks if the admin group exists and has all permissions
        """

        admin_group_query = Group.objects.filter(name="Admin")
        self.assertTrue(admin_group_query.exists())

    @patch("communications.clients.sms.NetgsmSMSClient.send_sms")
    @patch("communications.clients.email.DjangoEmailClient.send_email")
    def test_registration_with_phone(self, mock_send_email, mock_send_sms):
        mock_send_email.return_value = True
        mock_send_sms.return_value = True

        password = "password"
        confirm_password = "password"
        phone = "+905555555555"
        data = {
            "phone": phone,
            "password": password,
            "verify_password": confirm_password,
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
        password = "password"
        confirm_password = "password"
        email = "alper@yopmail.com"
        data = {
            "email": email,
            "password": password,
            "verify_password": confirm_password,
        }

        url = reverse("register")

        self.assertFalse(User.objects.filter(email=email).exists())

        response = self.client.post(url, data, format="json")

        self.assertTrue(User.objects.filter(email=email).exists())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("response_body").get("access"), None)

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
        self.assertNotEqual(response.data.get("response_body").get("access"), None)

    def test_login_with_invalid_phone(self):
        data = {"phone": "+905553330000", "password": "123"}

        url = reverse("login")

        self.assertTrue(User.objects.filter(phone=self.user.phone).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data.get("response_body").get("access"), None)

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
        self.assertNotEqual(response.data.get("response_body").get("access"), None)

    def test_login_with_invalid_email(self):
        data = {"email": "invalidemail@email.com", "password": self.email_password}

        url = reverse("login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data.get("response_body").get("access"), None)

    def test_login_unverified_user_fails_for_veification(self):
        self.email_user.email_verified = False
        self.email_user.save()
        data = {"email": self.email_user.email, "password": self.email_password}

        url = reverse("login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("response_body").get("access"), None)

    def test_login_unverified_user_succeeds(self):
        self.email_user.email_verified = False
        self.email_user.save()
        code = "213"
        contact_verification = baker.make(
            "contact_verification.ContactVerification",
            code=code,
            receiver_address=self.email_user.email,
            medium="email",
        )

        data = {
            "email": self.email_user.email,
            "password": self.email_password,
            "verification_code": code,
            "verification_id": contact_verification.id,
        }

        url = reverse("login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data.get("response_body").get("access"), None)

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
            email="myapp@yopmail.com",
        )

    @override_settings(GOOGLE_CLIENT_ID="google")
    @override_settings(SOCIAL_SECRET="social")
    @patch("authy.social_auth.google.Google.validate")
    def test_google_social_auth(self, mock_google_validate):
        mock_google_validate.return_value = {
            "sub": "abcdef",
            "aud": "google",
            "email": self.email_user.email,
            "name": self.email_user.fullname,
        }
        data = {"auth_token": "auth_token"}
        url = reverse("google_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

    @override_settings(GOOGLE_CLIENT_ID="google")
    @override_settings(SOCIAL_SECRET="social")
    @patch("authy.social_auth.google.Google.validate")
    def test_google_social_auth_new_user(self, mock_google_validate):
        mock_google_validate.return_value = {
            "sub": "abcdef",
            "aud": "google",
            "email": "new_google_user@yopmail.com",
            "name": "New User",
        }
        data = {"auth_token": "auth_token"}
        url = reverse("google_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            User.objects.filter(email="new_google_user@yopmail.com").exists()
        )

    @override_settings(SOCIAL_SECRET="social")
    @patch("authy.social_auth.facebook.Facebook.validate")
    def test_facebook_social_auth(self, mock_facebook_validate):
        mock_facebook_validate.return_value = {
            "id": "123456",
            "email": self.email_user.email,
            "name": self.email_user.fullname,
        }
        data = {"auth_token": "auth_token"}
        url = reverse("facebook_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

    @override_settings(SOCIAL_SECRET="social")
    @patch("authy.social_auth.facebook.Facebook.validate")
    def test_facebook_social_auth_new_user(self, mock_facebook_validate):
        mock_facebook_validate.return_value = {
            "id": "123456",
            "email": "new_facebook_user@yopmail.com",
            "name": "New User",
        }
        data = {"auth_token": "auth_token"}
        url = reverse("facebook_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            User.objects.filter(email="new_facebook_user@yopmail.com").exists()
        )

    @override_settings(SOCIAL_SECRET="social")
    @override_settings(APPLE_BUNDLE_ID="com.myapp.mobile")
    @patch("authy.social_auth.apple.Apple.validate")
    def test_apple_social_auth(self, mock_apple_validate):
        mock_apple_validate.return_value = {"email": self.email_user.email}
        data = {
            "auth_token": "eyJraWQiOiJZdXlYb1kiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FwcGxlaWQuYXBwbGUuY29tIiwiYXVkIjoiY29tLm15YXBwLm1vYmlsZSIsImV4cCI6OTk5OTk5OTk5OSwiaWF0IjoxNjk0NTYxNjA3LCJzdWIiOiIwMDEyMDEuNjJkNjkzZWE0NDZkNDMwNzgzNWQzOGM1YmMwNDkyNDEuMDgyMiIsImNfaGFzaCI6ImstZU5rcXhpMnRTbm1iV1BfaXJkUUEiLCJlbWFpbCI6Im15YXBwQHlvcG1haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOiJ0cnVlIiwiYXV0aF90aW1lIjoxNjk0NTYxNjA3LCJub25jZV9zdXBwb3J0ZWQiOnRydWV9.Rf50uJ1u8zF5MiGGMueGCk_Im_Cc4rWERIaRPLsQpvFUYcP4yc7sHvIZ3Yk7rmXgWC_fWCX7imm5PVg9mKlW3Q",
            "code": "code",
        }
        url = reverse("apple_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)

    @override_settings(SOCIAL_SECRET="social")
    @override_settings(APPLE_BUNDLE_ID="com.myapp.mobile")
    @patch("authy.social_auth.apple.Apple.validate")
    def test_apple_social_auth_new_user(self, mock_apple_validate):
        mock_apple_validate.return_value = {
            "email": "new_apple_user@yopmail.com",
        }
        data = {
            "auth_token": "eyJraWQiOiJZdXlYb1kiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FwcGxlaWQuYXBwbGUuY29tIiwiYXVkIjoiY29tLm15YXBwLm1vYmlsZSIsImV4cCI6OTk5OTk5OTk5OSwiaWF0IjoxNjk0NTYxNjA3LCJzdWIiOiIwMDEyMDEuNjJkNjkzZWE0NDZkNDMwNzgzNWQzOGM1YmMwNDkyNDEuMDgyMiIsImNfaGFzaCI6ImstZU5rcXhpMnRTbm1iV1BfaXJkUUEiLCJlbWFpbCI6Im15YXBwQHlvcG1haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOiJ0cnVlIiwiYXV0aF90aW1lIjoxNjk0NTYxNjA3LCJub25jZV9zdXBwb3J0ZWQiOnRydWV9.Rf50uJ1u8zF5MiGGMueGCk_Im_Cc4rWERIaRPLsQpvFUYcP4yc7sHvIZ3Yk7rmXgWC_fWCX7imm5PVg9mKlW3Q",
            "code": "code",
        }

        url = reverse("apple_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            User.objects.filter(email="new_apple_user@yopmail.com").exists()
        )
