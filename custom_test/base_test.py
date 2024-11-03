import uuid

from django.contrib.auth.models import Group, Permission
from django.db.models import Q
from django.test import TestCase
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APITestCase

from authy.models import Account
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
        account = baker.make(Account, id=uuid.uuid4())
        account.set_password(password)
        account.save()
        return baker.make(User, id=uuid.uuid4(), account=account, **kwargs), password

    def create_admin_user(self, password="123", **kwargs):
        user, password = self.create_user(password, **kwargs)
        user.account.groups.add(Group.objects.filter(name="Admin").first())
        user.account.save()

        return user, password

    def login_user(self, user: User, password: str):
        data = {"phone": user.phone, "password": password}
        url = reverse("login")
        response = self.client.post(url, data, format="json")
        return response.data["response_body"]

    def login_admin_user(self):
        return self.login_user(self.admin, self.admin_password)

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
                self.translation = product_query.first()
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
        self.user, self.user_password = self.create_user()
        self.admin, self.admin_password = self.create_admin_user()
        self.get_locale()
        self.create_product()
        self.translation = self.create_translation()


class CustomAPITestCase(CustomIntegrationTestCase, APITestCase):
    pass
