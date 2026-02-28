import uuid

from django.contrib.auth.models import Group, Permission
from django.db.models import Q
from django.test import TestCase
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APITestCase

from common.middlewares.global_context_middleware import GlobalContextMiddleware
from common.models import Locale
from common.models import Translation
from payment.models import Buyable
from user.models import User


class CustomIntegrationTestCase(TestCase):
    def setUp(self):
        self._phone_end = 0

    def generate_valid_phone_number(self):
        phone = 5550000000 + self._phone_end
        self._phone_end += 1
        return f"+90{phone}"

    def create_user_group(self, name="test_group", **kwargs):
        return baker.make(Group, name=name, **kwargs)

    def create_user_permission(self, name="test_permission", **kwargs):
        return baker.make(Permission, name=name, **kwargs)

    def create_user(self, password="123", **kwargs):
        if kwargs.get("phone", None) is None:
            phone = self.generate_valid_phone_number()
            kwargs["phone"] = phone
            kwargs["phone_verified"] = kwargs.get("phone_verified", True)
        if kwargs.get("email", None) is None:
            kwargs["email"] = f"user{uuid.uuid4()}@example.com"
        user = baker.make(User, id=uuid.uuid4(), **kwargs)
        user.set_password(password)
        user.save()
        return user, password

    def create_admin_user(self, password="123", **kwargs):
        user, password = self.create_user(password, **kwargs)
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        user.groups.add(admin_group)
        user.is_staff = True
        user.is_superuser = True
        user.save()

        return user, password

    def login_user(self, user: User, password: str):
        if user.phone:
            phone_str = str(user.phone)
            data = {"phone": phone_str, "password": password}
        else:
            data = {"email": user.email, "password": password}
        url = reverse("login")
        response = self.client.post(url, data, format="json")
        return response.data["response_body"]

    def login_admin_user(self):
        return self.login_user(self.admin, self.admin_password)

    def create_standard_users(self):
        """Creates self.user/self.user_password and self.admin/self.admin_password only. Does NOT create locale,
        product, or translation — do that inline in setUp.
        """
        self.user, self.user_password = self.create_user()
        self.admin, self.admin_password = self.create_admin_user()

    def authenticate_as(self, user):
        """Force-authenticate without HTTP. Use for all non-auth tests."""
        self.client.force_authenticate(user=user)

    def set_global_context(self, user):
        """Set GlobalContext for tests that need it (e.g., permission or log output tests). Automatically cleaned up in
        tearDown.
        """
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.user = user
        mock_request.auth = MagicMock()
        mock_request.auth.payload = {
            "user_id": str(user.id),
            "groups": [g.name for g in user.groups.all()],
            "permissions": list(user.get_all_permissions()),
            "locale_code": getattr(user, "locale_code", "en"),
        }
        mock_request.META = {"HTTP_USER_TIMEZONE": "UTC"}
        mock_request.GET = {}

        from common.middlewares.global_context_middleware import GlobalContext

        context = GlobalContext(mock_request)
        GlobalContextMiddleware.set_global_context(context)
        self.addCleanup(GlobalContextMiddleware.del_global_context)

    def get_locale(self):
        self.locale = Locale.objects.filter().first()

    def create_translation(self, id=None, text="translation", locale_id=None, **kwargs):
        translation_query = Translation.objects.filter(Q(id=id) | Q(text=text))
        if locale_id is not None:
            kwargs.setdefault("locale_id", locale_id)
        if translation_query.count() > 0:
            return translation_query.first()
        return (
            baker.make(Translation, id=id, text=text, root_id=id, **kwargs)
            if id
            else baker.make(Translation, text=text, root_id=id, **kwargs)
        )

    def create_product(
        self, id=None, name="product", title_id=1, description_id=1, **kwargs
    ):
        if not Translation.objects.filter(id=title_id):
            title = self.create_translation()
            title_id = title.id

        if not Translation.objects.filter(id=description_id):
            description = self.create_translation()
            description_id = description.id

        product_query = Buyable.objects.filter(id=id)
        if product_query.count() > 0:
            if not hasattr(self, "product"):
                self.product = product_query.first()
            product_query.update(
                name=name, title_id=title_id, description_id=description_id, **kwargs
            )
        self.product = (
            baker.make(
                Buyable,
                id=id,
                name=name,
                title_id=title_id,
                description_id=description_id,
                **kwargs,
            )
            if id
            else baker.make(
                Buyable,
                name=name,
                title_id=title_id,
                description_id=description_id,
                **kwargs,
            )
        )

    def create_common_models(self):
        """Deprecated. Use create_standard_users() + explicit baker.make() calls instead."""
        self.create_standard_users()
        self.locale = Locale.get_default()
        self.translation = baker.make(Translation, locale=self.locale)
        self.product = baker.make(
            Buyable,
            name="product",
            title=self.translation,
            description=self.translation,
        )


class CustomAPITestCase(CustomIntegrationTestCase, APITestCase):
    pass
