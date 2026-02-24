from typing import List

from celery import shared_task
from django.conf import settings
from structlog import get_logger

from communications.clients.email import BaseEmailClient, DjangoEmailClient
from communications.clients.sms import BaseSMSClient

log = get_logger(__name__)


@shared_task
def send_email_task(
    receivers: List[str],
    subject: str,
    message: str,
    from_email: str = None,
    html_message: str = None,
):
    actual_from_email = from_email or settings.EMAIL_HOST_USER
    client = DjangoEmailClient()
    try:
        return client.send_email(
            subject=subject,
            message=message,
            recipient_list=receivers,
            from_email=actual_from_email,
            html_message=html_message,
        )
    except Exception:
        log.error(
            "send_email_task_failed",
            exc_info=True,
            receivers=receivers,
            subject=subject,
        )
        raise


class BaseCommunicationService:
    def __init__(self, client):
        self._client = client

    def send(self, receivers: List[str], message: str, header: str, **kwargs) -> bool:
        return self._send(receivers=receivers, message=message, header=header, **kwargs)

    def _send(self, receivers, message, header, **kwargs) -> bool:
        raise NotImplementedError()

    def send_async(
        self, receivers: List[str], message: str, header: str, **kwargs
    ) -> bool:
        raise NotImplementedError()


class EmailService(BaseCommunicationService):
    def __init__(self, client: BaseEmailClient = None):
        super().__init__(client or DjangoEmailClient())

    def _send(
        self,
        receivers: List[str],
        message: str,
        header: str,
        from_email: str = None,
        html_message: str = None,
        **kwargs,
    ) -> bool:
        actual_from_email = from_email or settings.EMAIL_HOST_USER
        return self._client.send_email(
            subject=header,
            message=message,
            recipient_list=receivers,
            from_email=actual_from_email,
            html_message=html_message,
        )

    def send_async(
        self,
        receivers: List[str],
        subject: str,
        message: str,
        from_email: str = None,
        html_message: str = None,
        **kwargs,
    ):
        return send_email_task.delay(
            receivers=receivers,
            subject=subject,
            message=message,
            from_email=from_email,
            html_message=html_message,
        )


class SMSService(BaseCommunicationService):
    def __init__(self, client: BaseSMSClient):
        super().__init__(client)

    def _send(
        self, receivers: List[str], message: str, header: str, language="en", **kwargs
    ) -> bool:
        return self._client.send_sms(
            receiver=",".join(map(lambda x: x.replace("+", "00"), receivers)),
            language=language,
            message=message,
            header=header,
        )

    def send_async(
        self, receivers: List[str], message: str, header: str, **kwargs
    ) -> bool:
        return self._send(receivers=receivers, message=message, header=header, **kwargs)
