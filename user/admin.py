from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from user.models import User


class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("fullname", "phone", "locale")}),
        (_("Verification"), {"fields": ("email_verified", "phone_verified")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "created", "updated")}),
        (_("Other"), {"fields": ("creation_type", "deleted_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
    list_display = ("email", "fullname", "is_staff", "is_active", "created")
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "email_verified",
        "phone_verified",
        "creation_type",
    )
    search_fields = ("email", "fullname", "phone")
    ordering = ("email",)
    readonly_fields = ("created", "updated", "last_login")


admin.site.register(User, UserAdmin)
