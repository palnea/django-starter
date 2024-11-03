from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def run_after_migrations(sender, **kwargs):
    if sender == apps.get_app_config("auth"):
        # Create the Admin group with all permissions
        create_admin_group_with_all_permissions()


def create_admin_group_with_all_permissions():
    # Ensure the Admin group exists
    Group.objects.get_or_create(name="Admin")
