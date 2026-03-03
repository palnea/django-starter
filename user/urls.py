from django.urls import path

from .views import (
    UserViewSet,
)

app_name = "user"

user_detail = UserViewSet.as_view(
    {"patch": "partial_update", "delete": "destroy", "get": "retrieve"}
)
user_list = UserViewSet.as_view({"get": "list"})

urlpatterns = [
    path("", user_list, name="user-viewset"),
    path("<str:user_id>/", user_detail, name="user-detail-viewset"),
]
