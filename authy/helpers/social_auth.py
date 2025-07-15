from django.conf import settings

from authy.helpers.token_helper import social_auth_authenticate_user
from user.models import User
from user.types import UserCreationType


def login_social_user(provider, user_id, email, name, contact_permission=False):
    filtered_user_by_email = User.objects.filter(email=email)
    password = settings.SOCIAL_SECRET

    if filtered_user_by_email.exists():
        user = filtered_user_by_email[0]
    else:
        data = {
            "email": email,
            "password": password,
            "fullname": name or "",
        }
        user = User.create_with_password(data=data)
        # Set additional social auth specific fields
        user.email_verified = True  # Email is verified through social provider
        user.creation_type = UserCreationType.PERSONAL
        user.save()
    return social_auth_authenticate_user(user)
