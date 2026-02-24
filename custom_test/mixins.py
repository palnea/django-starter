from django.urls import reverse
from rest_framework import status


class CRUDPermissionTestsMixin:
    """Provides standard CRUD permission tests for admin-write / public-read resources.

    Subclasses must define:
        list_url_name: str          — URL name for list/create endpoint
        detail_url_name: str        — URL name for retrieve/update/delete endpoint
        detail_url_kwarg: str       — URL kwarg name (default "id")
        create_data: dict           — POST payload for create tests
        update_data: dict           — PATCH payload for update tests
        resource_factory(): obj     — returns an existing instance for detail tests

    Optional overrides:
        unauthenticated_read_allowed: bool  (default True — public read)
        regular_user_read_allowed: bool     (default True)
    """

    detail_url_kwarg = "id"
    unauthenticated_read_allowed = True
    regular_user_read_allowed = True

    def get_list_url(self):
        return reverse(self.list_url_name)

    def get_detail_url(self, obj):
        return reverse(self.detail_url_name, kwargs={self.detail_url_kwarg: obj.id})

    # --- Regular user ---

    def test_regular_user_can_list(self):
        self.authenticate_as(self.user)
        response = self.client.get(self.get_list_url())
        expected = (
            status.HTTP_200_OK
            if self.regular_user_read_allowed
            else status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(response.status_code, expected)

    def test_regular_user_can_retrieve(self):
        obj = self.resource_factory()
        self.authenticate_as(self.user)
        response = self.client.get(self.get_detail_url(obj))
        expected = (
            status.HTTP_200_OK
            if self.regular_user_read_allowed
            else status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(response.status_code, expected)

    def test_regular_user_cannot_create(self):
        self.authenticate_as(self.user)
        response = self.client.post(
            self.get_list_url(), self.create_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_update(self):
        obj = self.resource_factory()
        self.authenticate_as(self.user)
        response = self.client.patch(
            self.get_detail_url(obj), self.update_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_delete(self):
        obj = self.resource_factory()
        self.authenticate_as(self.user)
        response = self.client.delete(self.get_detail_url(obj), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(obj.__class__.objects.filter(id=obj.id).exists())

    # --- Unauthenticated user ---

    def test_unauthenticated_user_can_list(self):
        self.authenticate_as(None)
        response = self.client.get(self.get_list_url())
        expected = (
            status.HTTP_200_OK
            if self.unauthenticated_read_allowed
            else status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(response.status_code, expected)

    def test_unauthenticated_user_can_retrieve(self):
        obj = self.resource_factory()
        self.authenticate_as(None)
        response = self.client.get(self.get_detail_url(obj))
        expected = (
            status.HTTP_200_OK
            if self.unauthenticated_read_allowed
            else status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(response.status_code, expected)

    def test_unauthenticated_user_cannot_create(self):
        self.authenticate_as(None)
        response = self.client.post(
            self.get_list_url(), self.create_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_user_cannot_update(self):
        obj = self.resource_factory()
        self.authenticate_as(None)
        response = self.client.patch(
            self.get_detail_url(obj), self.update_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_user_cannot_delete(self):
        obj = self.resource_factory()
        self.authenticate_as(None)
        response = self.client.delete(self.get_detail_url(obj), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(obj.__class__.objects.filter(id=obj.id).exists())
