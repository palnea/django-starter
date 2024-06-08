from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status

from common.custom_exceptions.custom_exception import CustomException
from common.models import Translation
from common.response.response_information_codes.error_code import ErrorCode
from user.models import User, School, Class
from user.types import UserRole
from utils.converters import FileConverter


class AvatarSerializer(serializers.Serializer):
    image = serializers.CharField(required=True)

    def validate(self, attrs):
        image = attrs.get("image")
        if image:
            try:
                image_file, ext = FileConverter.ImageBase64ToBytes(image)
                if not image_file or not ext:
                    serializers.ValidationError("Couldn't get image_file or extension!")
            except Exception as e:
                serializers.ValidationError(str(e))

        validated_data = {"image": image}

        return validated_data


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = "__all__"

    def to_representation(self, instance):
        from .serializers import SchoolSerializer

        self.fields["school"] = SchoolSerializer(read_only=True)

        return super(UserSerializer, self).to_representation(instance)


class UserPartialUpdateSerializer(serializers.ModelSerializer):
    fullname = serializers.CharField(required=False, max_length=50)
    avatar_id = serializers.IntegerField(required=False, allow_null=False)
    role = serializers.ChoiceField(choices=UserRole.choices, required=False)
    school_id = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["fullname", "avatar_id", "role", "school_id"]

    def validate(self, attrs):
        validated_data = attrs
        user_id = (
            self.context.get("request").parser_context.get("kwargs", {}).get("user_id")
        )
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            raise serializers.ValidationError("User not found!")

        user_role = (
            self.context.get("request").auth.payload.get("role", "none")
            if self.context.get("request") and self.context.get("request").auth
            else "none"
        )

        if attrs.get("role", None) and (
            UserRole(user_role) < UserRole.EDITOR
            or UserRole(attrs.get("role", "none")) > UserRole(user_role)
            or UserRole(user.role) > UserRole(user_role)
        ):
            raise CustomException(
                detail={"error": "You do not have permission to edit"},
                code=ErrorCode.PERMISSION_DENIED,
                status_code=status.HTTP_403_FORBIDDEN,
                message=_("You don't have permission for this action!"),
            )

        validated_data.update({"user": user})
        return validated_data


class SchoolSerializer(serializers.ModelSerializer):
    name_id = serializers.PrimaryKeyRelatedField(
        source="name",
        queryset=Translation.objects.all(),
        write_only=True,
        required=True,
        allow_null=False,
    )

    class Meta:
        model = School
        fields = "__all__"
        read_only_fields = ["name"]

    def to_representation(self, instance: School):
        """
        Modify the output representation of the serializer to return name_id.
        """
        representation = super().to_representation(instance)
        representation["name_id"] = instance.name.id if instance.name else None

        if hasattr(instance, "translated_name") and instance.translated_name:
            representation["name"] = instance.translated_name[0].text
        return representation


class ClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = "__all__"


class SchoolRetrieveSerializer(SchoolSerializer):
    classes = ClassSerializer(many=True)
