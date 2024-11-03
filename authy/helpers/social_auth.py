from django.conf import settings

from authy.helpers.token_helper import social_auth_authenticate_user
from user.models import User


def login_social_user(provider, user_id, email, name, contact_permission=False):
    filtered_user_by_email = User.objects.filter(email=email)
    password = settings.SOCIAL_SECRET

    if filtered_user_by_email.exists():
        user = filtered_user_by_email[0]
    else:
        data = {
            "email": email,
            "password": password,
            "auth_provider": provider,
            "contact_permission": contact_permission,
        }
        user = User.create_with_account(data=data)
    return social_auth_authenticate_user(user)
