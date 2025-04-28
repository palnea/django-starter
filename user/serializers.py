from rest_framework import serializers

from user.models import User


class UserSerializer(serializers.ModelSerializer):
    deleted_at = serializers.DateTimeField(
        read_only=True, required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = "__all__"


class UserPartialUpdateSerializer(serializers.ModelSerializer):
    fullname = serializers.CharField(required=False, max_length=50)

    class Meta:
        model = User
        fields = ["fullname"]

    def validate(self, attrs):
        validated_data = attrs
        user_id = (
            self.context.get("request").parser_context.get("kwargs", {}).get("user_id")
        )
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            raise serializers.ValidationError("User not found!")

        validated_data.update({"user": user})
        return validated_data
