from typing import TYPE_CHECKING

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

if TYPE_CHECKING:
    from user.models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def create(self, validated_date):
        pass

    def update(self, instance, validated_data):
        pass

    @classmethod
    def get_token(cls, user: "User", user_obj: "User"):
        token = super().get_token(user)

        token["email"] = user.email
        token["phone"] = user.phone and user.phone.as_international.replace(" ", "")
        token["user_id"] = str(user.id)
        token["groups"] = list(user.groups.values_list("name", flat=True))
        token["permissions"] = list(
            user.user_permissions.values_list("codename", flat=True)
        )

        return token
