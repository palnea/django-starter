from typing import List

from django.conf import settings

from communications.clients.email import BaseEmailClient
from communications.clients.sms import BaseSMSClient
from utils.decorators.executional import call_async


class BaseCommunicationService:
    def __init__(self, client):
        self._client = client

    def _send(self, receivers, message, header, **kwargs) -> bool:
        raise NotImplementedError()

    def send(self, receivers: List[str], message: str, header: str, **kwargs) -> bool:
        return self._send(receivers=receivers, message=message, header=header, **kwargs)

    @call_async
    def send_async(
        self, receivers: List[str], message: str, header: str, **kwargs
    ) -> bool:
        return self._send(receivers=receivers, message=message, header=header, **kwargs)


class EmailService(BaseCommunicationService):
    def __init__(self, client: BaseEmailClient):
        super().__init__(client)

    def _send(
        self,
        receivers: str,
        message: str,
        header: str,
        from_email: str = settings.EMAIL_HOST_USER,
        html_message: str = None,
        **kwargs
    ) -> bool:
        return self._client.send_email(
            subject=header,
            message=message,
            recipient_list=receivers,
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
