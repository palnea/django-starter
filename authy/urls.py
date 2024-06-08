from django.urls import path

from .views import (
    UserLoginView,
    UserRegisterView,
    PasswordViewSet,
    UpdatePasswordViewSet,
    CustomTokenRefreshView, GoogleSocialAuthView, FacebookSocialAuthView, AppleSocialAuthView,
)

password_view_set = PasswordViewSet.as_view({"post": "reset_password"})
update_password_viewset = UpdatePasswordViewSet.as_view({"post": "create"})

urlpatterns = [
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("login", UserLoginView.as_view(), name="login"),
    path("register", UserRegisterView.as_view(), name="register"),
    path("reset_password", password_view_set, name="reset_password"),
    path("update_password/", update_password_viewset, name="update_password"),
    path("google/", GoogleSocialAuthView.as_view(), name="google_social_auth"),
    path("facebook/", FacebookSocialAuthView.as_view(), name="facebook_social_auth"),
    path("apple/", AppleSocialAuthView.as_view(), name="apple_social_auth"),
]
