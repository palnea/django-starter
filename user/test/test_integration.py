from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from mock.mock import patch
from model_bakery import baker
from rest_framework import status

from custom_test.base_test import CustomIntegrationTestCase
from user.models import Avatar, School, Class, User


class AvatarViewSetTestCase(CustomIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.create_common_models()
        self.assign_permissions_to_admin_group()

    def assign_permissions_to_admin_group(self):
        group = Group.objects.get(name="Admin")
        group.permissions.add(
            Permission.objects.get(codename="can_write_avatar", content_type__app_label="user"),
        )

    def test_list_avatars(self):
        url = reverse("avatar-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("cloud_storage.idrive_client.IDriveClient.create_presigned_url")
    def test_create_avatar(self, mock_create_presigned_url):
        presigned_response = "https://example.com/avatar.png"
        mock_create_presigned_url.return_value = presigned_response
        login_response = self.login_admin_user()
        url = reverse("avatar-viewset")

        data = {
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAEaUlEQVR4nLzW+1NUZRwGcLYWlRwQEcRQiqtcJikWGSAwrnJTghxiRhxuKYNmQOGEBQ7iNiiBulwWkgEBSQUKlDAxTdigdgAvLBq4FSBla4FrrIA3dKGe54/o8MPnHXbP2fk+57zv933FDnt+MTAwKD06Dr0l56D+sydwUPYNlEgs4RqLtdAiQApdlPzWVT4El9s7QWf/CbijvBT2KuqgPPEQfFmzAb5g8D//iQ+8zdpTFhbD2lwXaHb4S+hXsQq2fHUc3r3Eeo9rY+CGylEmrjCHpncTYEn6GFx6mp8nN66ApwIyeFdTtBAJRLt7X8UwElMMtb374VgMn3V8Wxur28naNb6s40FmHvRU3IN2s1tYtXMwdK/bCXvcZuCAugCa22fCgk5/IRKIbXbbYigdjoWOj2tgQ38f9G66AJ26UqA+linzvGrhx41q+G/w91DWegtKRqZZtfIK71J6wojbvD7LNF6IBCKHo/0Y7JoCYY3VRla9cTVUPQqAN4xSYecNXtOYNMUbVM/gdSdXGOtqB9OrmPvk3ErYHDbLZJbGsCzhXSESiHOuvYTBZUs+DM99yKrXcU24Vx+ByRprOOTGeTKtfRGO2evh6Xm+g9mUZljvtQtOlEnggIzJ9LIw6JHyoxAJREu/qMLgU+wN+6TZ0ERRBouvciV//v4duF53Al54/B3MCOqCU33tcOVqezgzPwwv2o/ALq834Scm+2DP9lxBEkjVH2HokLTAxHB2HmcxZ5Fk6gMYpfkQ3kvjbInb1gAnB5hjwulPGDpcDrPjEuGnJ+rhoNgQmskewKS/fxYigViq4LMbUmph5Sg7a4DUBD4fdYARcvb0QCvOrhWO7C2T1b3Q2qoHzk8o4G857Ky1FTr4qxf78XTI69Anql2IBKJUY86BoHeU/C+UO9o2X3bEludyuMbEBqb0q1i7Id9QhBl3haQhpox+yHvXxXPWF2YyU/kPfO5rl/HXJPvqBElg2Ml5XfAWV6BReDiUSiZZ73w1vK8ugmcO+LHqY1zh8v3sS6KyIGhxbjvUJnM1ZPhx3YxnslNVKbhb6BQtQiQQF11m9y+5yL0s+hD3rNn6S7BZ9Ts0WcUuf/gm94Zbd7ph4MmzUCXl2m6cuw2D0zbDZwUd0GEvzxlpu7g+jDw9hEggOj+zCMM1KU8yWXlfw4O2nNHnf+JOcDWf+8TCdR8Yl7AAi977B367id0mUM7rM9x5Cjmoc4PKLD73v/J5jorseU2IBOInZ3meUb/BziM14iz6Y9gXblaz9iLLerjkvju84lsCwyLXw0Wm/Fa/ZBMcnePJrqW6ESq2noK2Or5Xh9QuQRIYD7Lb5Ponw840Z9h+ZAc0D+UOJRsJgFbLefKoCbGBvQuXYWFsCNQt5grf25oOowbY/QuPPYV9idyNXyl4JEiCcSfODZ0H12T3MtrWwI60p4M9vVvDHa20nh3fKIfvptKQOayCQ5mv9Sbc2scdMLL6DHR8yrvMiiL4m9nWQiT4LwAA//9Pf4XQ0CrQ/gAAAABJRU5ErkJggg=="
        }

        avatar_count = Avatar.objects.count()
        response = self.client.post(
            url,
            data,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {login_response.get('access')}",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data.get("response_body").get("image"), presigned_response
        )
        avatar_count_after_create = Avatar.objects.count()
        self.assertEqual(avatar_count_after_create, avatar_count + 1)


class SchoolViewSetTestCase(CustomIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.create_common_models()
        self.school = baker.make(
            "user.School", name=self.translation, type=School.PUBLIC
        )

        response = self.login_admin_user()
        self.access_token = response.get("access", None)
        self.assign_permissions_to_admin_group()

    def assign_permissions_to_admin_group(self):
        group = Group.objects.get(name="Admin")
        group.permissions.add(
            Permission.objects.get(codename="can_write_school", content_type__app_label="user"),
        )

    def test_list_schools(self):
        url = reverse("school-viewset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_create_school(self):
        data = {"name_id": self.translation.id, "type": "PUBLIC"}

        school_count = School.objects.count()
        url = reverse("school-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        school_count_after_create = School.objects.count()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(school_count_after_create, school_count + 1)

    def test_retrieve_school(self):
        school = School.objects.first()
        url = reverse("school-detail-viewset", kwargs={"id": school.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("response_body").get("id"), str(school.id))

    def test_partial_update_school(self):
        school = School.objects.first()
        url = reverse("school-detail-viewset", kwargs={"id": school.id})
        locale = baker.make("common.Locale", name="England", code="en")
        new_name = self.create_translation(text="New school name", locale_id=locale.id)
        response = self.client.patch(
            url,
            {"name_id": new_name.id},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        school = School.objects.get(id=school.id)
        self.assertEqual(new_name.text, school.name.text)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_school(self):
        school = School.objects.first()
        url = reverse("school-detail-viewset", kwargs={"id": school.id})
        self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertFalse(School.objects.filter(id=school.id).exists())


class ClassViewSetTestCase(CustomIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.create_common_models()
        self.school = baker.make(
            "user.School", name=self.translation, type=School.PUBLIC
        )
        self.example_class = baker.make("user.Class", branch="A", school=self.school)
        self.school2 = baker.make(
            "user.School", name=self.translation, type=School.PRIVATE
        )
        self.example_class2 = baker.make("user.Class", branch="C", school=self.school2)

        response = self.login_admin_user()
        self.access_token = response.get("access", None)
        self.assign_permissions_to_admin_group()

    def assign_permissions_to_admin_group(self):
        group = Group.objects.get(name="Admin")
        group.permissions.add(
            Permission.objects.get(codename="can_write_class", content_type__app_label="user"),
        )

    def test_list_classes(self):
        url = reverse("class-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_create_class(self):
        data = {"branch": "STH", "school": str(self.school2.id)}

        class_count = Class.objects.count()
        url = reverse("class-viewset")
        response = self.client.post(
            url, data, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        class_count_after_create = Class.objects.count()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(class_count_after_create, class_count + 1)

    def test_retrieve_class(self):
        created_class = Class.objects.first()
        url = reverse("class-detail-viewset", kwargs={"id": created_class.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), str(created_class.id)
        )

    def test_partial_update_class(self):
        created_class = Class.objects.first()
        url = reverse("class-detail-viewset", kwargs={"id": created_class.id})
        branch = "Newbies"
        response = self.client.patch(
            url,
            {"branch": branch},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        updated_class = Class.objects.get(id=created_class.id)
        self.assertEqual(branch, updated_class.branch)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_class(self):
        created_class = Class.objects.first()
        url = reverse("class-detail-viewset", kwargs={"id": created_class.id})
        self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertFalse(Class.objects.filter(id=created_class.id).exists())


class UserViewSetTestCase(CustomIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.create_common_models()
        response = self.login_admin_user()
        self.access_token = response.get("access", None)
        self.assign_permissions_to_admin_group()

    def assign_permissions_to_admin_group(self):
        group = Group.objects.get(name="Admin")
        group.permissions.add(
            Permission.objects.get(codename="can_write_user", content_type__app_label="user"),
        )

    def test_list_users(self):
        url = reverse("user-viewset")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get("response_body")), 1)

    def test_retrieve_user(self):
        created_user = User.objects.first()
        url = reverse("user-detail-viewset", kwargs={"user_id": created_user.id})
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("response_body").get("id"), str(created_user.id)
        )

    def test_partial_update_user(self):
        created_user = User.objects.first()
        url = reverse("user-detail-viewset", kwargs={"user_id": created_user.id})
        fullname = "teacher"
        response = self.client.patch(
            url,
            {"fullname": fullname},
            content_type="application/json",
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        updated_user = User.objects.get(id=created_user.id)
        self.assertEqual(fullname, updated_user.fullname)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_user(self):
        created_user = User.objects.first()
        url = reverse("user-detail-viewset", kwargs={"user_id": created_user.id})
        self.client.delete(
            url, format="json", HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )
        self.assertFalse(User.objects.filter(id=created_user.id).exists())
