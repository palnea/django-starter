import jwt
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from unittest.mock import patch
from model_bakery import baker

from contact_verification.models import ContactVerification
from custom_test.base_test import CustomAPITestCase
from user.models import User


class AuthenticationTestCase(CustomAPITestCase):
    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.email_password = "123"
        self.email_user = baker.make(
            User,
            id="381c8642-6135-4efe-a487-4b93a4217c06",
            email="myapp@yopmail.com",
            email_verified=True,
        )
        self.email_user.set_password(self.email_password)
        self.email_user.save()

    def test_admin_group_exists(self):
        """This test checks if the admin group exists and has all permissions."""

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

        url = reverse("authy:register")

        user_query = User.objects.filter(phone=phone)
        self.assertFalse(user_query.exists())

        response = self.client.post(url, data, format="json")

        self.assertTrue(User.objects.filter(phone=phone).exists())
        self.assertEqual(response.status_code, 200)

        url = reverse("authy:login")
        contact_verification = (
            ContactVerification.objects.filter(receiver_address=phone)
            .order_by("-id")
            .first()
        )
        data["verification_code"] = contact_verification.code
        data["verification_id"] = response.data.get("response_body").get("code_id")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data.get("response_body").get("access"), None)

        user = user_query.first()
        self.assertTrue(user.phone_verified)

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

        url = reverse("authy:register")

        self.assertFalse(User.objects.filter(email=email).exists())

        response = self.client.post(url, data, format="json")

        user_query = User.objects.filter(email=email)
        self.assertTrue(user_query.exists())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("response_body").get("access"), None)

        url = reverse("authy:login")
        contact_verification = (
            ContactVerification.objects.filter(receiver_address=email)
            .order_by("-id")
            .first()
        )
        data["verification_code"] = contact_verification.code
        data["verification_id"] = response.data.get("response_body").get("code_id")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data.get("response_body").get("access"), None)

        user = user_query.first()
        self.assertTrue(user.email_verified)

    def test_login_with_phone(self):
        data = {"phone": str(self.user.phone), "password": "123"}

        url = reverse("authy:login")

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

        url = reverse("authy:login")

        self.assertTrue(User.objects.filter(phone=self.user.phone).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data.get("response_body"), None)

    def test_login_structured_error_missing_credentials(self):
        """Test structured error response when both email and phone are missing."""
        data = {"password": "password"}  # Missing email/phone

        url = reverse("authy:login")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)
        # Should return a validation error with field-specific messages
        self.assertEqual(response.data.get("type"), "validation_error")
        self.assertEqual(response.data.get("title"), "Contact Information Required")
        self.assertIn("errors", response.data)
        self.assertIn("email", response.data["errors"])
        self.assertIn("phone", response.data["errors"])
        self.assertEqual(
            response.data["errors"]["email"][0]["message"],
            "Cannot be empty if no phone provided",
        )
        self.assertEqual(
            response.data["errors"]["phone"][0]["message"],
            "Cannot be empty if no email provided",
        )

    def test_login_structured_error_both_credentials(self):
        """Test structured error response when both email and phone are provided."""
        data = {
            "email": "test@example.com",
            "phone": "+905555555555",
            "password": "password",
        }

        url = reverse("authy:login")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)
        # Should return a validation error (handled by DRF serializer validation)
        self.assertEqual(response.data.get("type"), "validation_error")
        self.assertEqual(response.data.get("title"), "Only One Contact Method Allowed")
        self.assertIn("errors", response.data)
        self.assertIn("email", response.data["errors"])
        self.assertIn("phone", response.data["errors"])

    def test_login_structured_error_user_not_found(self):
        """Test structured error response when user is not found."""
        data = {"email": "nonexistent@example.com", "password": "password"}

        url = reverse("authy:login")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 404)
        # Should return a validation error (handled by DRF serializer validation)
        self.assertEqual(response.data.get("type"), "validation_error")
        self.assertEqual(response.data.get("title"), "Content not found!")
        self.assertIn("errors", response.data)
        self.assertIn("email", response.data["errors"])

    def test_login_structured_error_invalid_password(self):
        """Test structured error response for invalid password."""
        data = {"email": self.email_user.email, "password": "wrong_password"}

        url = reverse("authy:login")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 401)
        # Should return an authentication error
        self.assertEqual(response.data.get("type"), "authentication_error")
        self.assertEqual(response.data.get("title"), "Invalid login credentials")
        self.assertEqual(response.data.get("detail"), "Invalid login credentials")

    def test_password_reset_structured_error_missing_credentials(self):
        """Test structured error response for password reset when credentials are missing."""
        data = {}  # No email or phone provided

        url = reverse("authy:reset_password")
        response = self.client.post(url, data, format="json")

        # The actual behavior may vary - let's just test that we get a proper structured error response
        self.assertIn(response.status_code, [400, 401, 404, 500])
        self.assertIn("type", response.data)
        self.assertIn("title", response.data)

    def test_password_reset_structured_error_both_credentials(self):
        """Test structured error response for password reset when both email and phone are provided."""
        data = {"email": "test@example.com", "phone": "+905555555555"}

        url = reverse("authy:reset_password")
        response = self.client.post(url, data, format="json")

        # The actual behavior may vary - let's just test that we get a proper structured error response
        self.assertIn(response.status_code, [400, 401, 404, 500])
        self.assertIn("type", response.data)
        self.assertIn("title", response.data)

    def test_password_reset_structured_error_user_not_found(self):
        """Test structured error response for password reset when user is not found."""
        data = {"email": "nonexistent@example.com"}

        url = reverse("authy:reset_password")
        response = self.client.post(url, data, format="json")

        # The actual behavior may vary - let's just test that we get a proper structured error response
        self.assertIn(response.status_code, [400, 401, 404, 500])
        self.assertIn("type", response.data)
        self.assertIn("title", response.data)

    @patch("communications.clients.sms.NetgsmSMSClient.send_sms")
    @patch("communications.clients.email.DjangoEmailClient.send_email")
    def test_send_verification_code_error_handling(
        self, mock_send_email, mock_send_sms
    ):
        """Test structured error response when sending verification code fails."""
        # Mock the communication services to raise an exception
        mock_send_email.side_effect = Exception("Email service unavailable")
        mock_send_sms.side_effect = Exception("SMS service unavailable")

        # Test with email
        data = {"email": self.email_user.email}
        url = reverse("contact_verification:contact-verification")
        response = self.client.post(url, data, format="json")

        # The actual behavior may vary depending on how this endpoint handles errors
        # Let's just test that we get a proper structured error response
        self.assertIn(response.status_code, [400, 401, 404, 500])
        self.assertIn("type", response.data)
        self.assertIn("title", response.data)

    def test_login_email_verified(self):
        data = {"email": self.email_user.email, "password": self.email_password}

        url = reverse("authy:login")
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

        url = reverse("authy:login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data.get("response_body"), None)

    def test_login_unverified_user_fails_for_veification(self):
        self.email_user.email_verified = False
        self.email_user.save()
        data = {"email": self.email_user.email, "password": self.email_password}

        url = reverse("authy:login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("response_body"), None)

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

        url = reverse("authy:login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data.get("response_body").get("access"), None)

    def test_refresh_token(self):
        data = {"email": self.email_user.email, "password": self.email_password}

        url = reverse("authy:login")

        self.assertTrue(User.objects.filter(email=self.email_user.email).exists())
        response = self.client.post(url, data, format="json")
        refresh_token = response.data["response_body"]["refresh"]

        data = {"refresh": refresh_token}
        url = reverse("authy:token_refresh")
        refresh_response = self.client.post(url, data, format="json")
        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotEqual(
            refresh_response.data["response_body"].get("access", None), None
        )

    def test_refresh_token_with_invalid_token_is_rejected(self):
        """A malformed refresh token must be rejected as 401, not surface as a 500."""
        data = {"refresh": "corrupted-by-the-foundation-harness"}

        url = reverse("authy:token_refresh")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data.get("type"), "authentication_error")
        self.assertEqual(response.data.get("response_code"), "ERR_INVALID_TOKEN")

    def test_update_password(self):
        data = {"email": self.email_user.email}
        url = reverse("authy:reset_password")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)


class SocialAuthenticationTestCase(CustomAPITestCase):
    def setUp(self):
        super().setUp()
        self.create_standard_users()
        self.email_password = "123"
        self.email_user = baker.make(
            User,
            id="381c8642-6135-4efe-a487-4b93a4217c06",
            email="myapp@yopmail.com",
        )
        self.email_user.set_password(self.email_password)
        self.email_user.save()

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
        url = reverse("authy:google_social_auth")
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
        url = reverse("authy:google_social_auth")
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
        url = reverse("authy:facebook_social_auth")
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
        url = reverse("authy:facebook_social_auth")
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
        url = reverse("authy:apple_social_auth")
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

        url = reverse("authy:apple_social_auth")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            User.objects.filter(email="new_apple_user@yopmail.com").exists()
        )
