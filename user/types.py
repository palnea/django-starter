from django.db import models


class UserCreationType(models.TextChoices):
    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"
    INTERNAL = "INTERNAL"
