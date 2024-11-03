from django.db import models

import settings
from communications.clients.email import DjangoEmailClient
from communications.clients.sms import get_sms_client
from communications.services.communication_services import EmailService, SMSService


class CommunicationMedium(models.TextChoices):
    EMAIL = "email"
    PHONE = "phone"


def get_communication_service(type: CommunicationMedium):
    COMMUNICATION_SERVICE_MAPPER = {
        CommunicationMedium.EMAIL: EmailService(DjangoEmailClient()),
        CommunicationMedium.PHONE: SMSService(get_sms_client()),
    }

    return COMMUNICATION_SERVICE_MAPPER.get(type, None)


def get_code_valid_period_by_medium(medium: CommunicationMedium):
    VALID_PERIOD_MAPPER = {
        CommunicationMedium.EMAIL: settings.EMAIL_VERIFICATION_ACTIVE_INTERVAL,
        CommunicationMedium.PHONE: settings.PHONE_VERIFICATION_ACTIVE_INTERVAL,
    }

    return VALID_PERIOD_MAPPER.get(medium, None)
