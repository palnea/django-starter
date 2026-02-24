import datetime
import random
import string
import uuid

from common.middlewares.global_context_middleware import GlobalContextMiddleware
from communications.services import CommunicationMedium, get_communication_service
from django.conf import settings
from django.db import models, transaction
from django.db.models import Q, UniqueConstraint
from django.template.loader import render_to_string
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _
from utils.fields import DateTimeWithoutTZField


# Create your models here.
class ContactVerification(models.Model):
    class Status(models.TextChoices):
        INITIAL = "initial"
        SENT = "sent"
        FAILED = "failed"
        VERIFIED = "verified"

    id = models.UUIDField(
        unique=True, primary_key=True, default=uuid.uuid4, editable=False
    )
    medium = models.CharField(
        null=False, blank=False, choices=CommunicationMedium.choices, max_length=64
    )
    receiver_address = models.CharField(null=False, blank=False, max_length=1024)
    code = models.CharField(max_length=6, null=False, blank=False)
    valid_interval_in_seconds = models.IntegerField(
        null=False, blank=False, default=300
    )
    attempts = models.IntegerField(null=False, blank=False, default=0)
    status = models.CharField(
        null=False,
        blank=False,
        choices=Status.choices,
        max_length=64,
        default=Status.INITIAL,
    )
    created = DateTimeWithoutTZField(auto_now_add=True, editable=False)
    updated = DateTimeWithoutTZField(auto_now=True, editable=False)

    class Meta:
        db_table = "contact_verification"
        constraints = [
            UniqueConstraint(
                fields=["code", "status"],
                condition=Q(status="initial") | Q(status="sent"),
                name="unique_code_status_when_not_finished",
            )
        ]

    @property
    def _active(self):
        latest_active_date = self.created + datetime.timedelta(
            seconds=self.valid_interval_in_seconds
        )
        return latest_active_date > datetime.datetime.utcnow()

    def generate_code(self):
        key = "".join(random.choice(string.digits) for x in range(6))
        earliest_active_day = datetime.datetime.utcnow() - datetime.timedelta(
            seconds=self.valid_interval_in_seconds
        )
        if ContactVerification.objects.filter(
            code=key, created__gt=earliest_active_day
        ).exists():
            key = self.generate_code()
        return key

    def get_sender(self):
        return get_communication_service(CommunicationMedium(self.medium))

    def get_email_html_message(self, verification_code: str, user_name: str):
        user_language = GlobalContextMiddleware.get_global_context().language_code
        activate(user_language)

        # Prepare context for email template
        context = {
            "verification_code": verification_code,
            "user_name": user_name,
            "expiry_time": settings.EMAIL_VERIFICATION_ACTIVE_INTERVAL,
            "logo_url": f"{settings.LOGO_URL}",
        }

        # Render email template with context
        return render_to_string("emails/verification_email.html", context)

    def send_code(self):
        if self.code:
            context = GlobalContextMiddleware.get_global_context()
            sender = self.get_sender()

            message = _("Verification code message").format(code=self.code)

            if self.medium == CommunicationMedium.EMAIL:
                email_html_message = self.get_email_html_message(
                    self.code, getattr(context.user, "fullname", "") or ""
                )
                sender.send_async(
                    receivers=[self.receiver_address],
                    subject=_("Verify Your Email"),
                    message=message,
                    html_message=email_html_message,
                )
            else:
                sender.send_async(
                    [self.receiver_address],
                    message,
                    settings.SMS_HEADER,
                )
            self.status = ContactVerification.Status.SENT
            self.save()

    @property
    def is_valid(self):
        """Returns if the code is valid Not valid if the code is already verified before Not valid if the limited time
        is passed.
        """
        if self.status == ContactVerification.Status.VERIFIED:
            return False
        now = datetime.datetime.utcnow()
        difference = now - self.created
        self.status = ContactVerification.Status.VERIFIED
        self.save()
        return difference < datetime.timedelta(seconds=self.valid_interval_in_seconds)

    @transaction.atomic
    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.code:
            self.code = self.generate_code()
        super().save(force_insert, force_update, using, update_fields)
