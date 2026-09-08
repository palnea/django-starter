# communications

[Back to docs index](../README.md)

Email and SMS delivery. A plain Python package, **not** an installed Django app,
so it has no models and no migrations.

---

## Shape

```
communications/
  clients/
    email.py    BaseEmailClient, DjangoEmailClient, get_email_service()
    sms.py      BaseSMSClient, NetgsmSMSClient, get_sms_client()
  services/
    __init__.py                CommunicationMedium, get_communication_service()
    communication_services.py  BaseCommunicationService, EmailService, SMSService,
                               send_email_task
```

Two layers. A **client** knows how to talk to one provider. A **service** is the
interface the rest of the codebase uses, and takes a client.

Unlike `{app}/services.py` elsewhere, these services **are** instantiated and
hold a client. They are adapters, not business logic. See
[../conventions/services.md](../conventions/services.md).

---

## Using it

By medium, which is what `contact_verification` does:

```python
from communications.services import CommunicationMedium, get_communication_service

sender = get_communication_service(CommunicationMedium.EMAIL)
sender.send_async(receivers=[address], subject=..., message=...)
```

Directly, which is what `authy` does:

```python
from communications.services.communication_services import EmailService, SMSService
from communications.clients.sms import get_sms_client

EmailService().send_async(
    receivers=[user.email],
    subject=_("Reset password title"),
    message=_("Reset password email message").format(password=password),
    from_email=settings.EMAIL_HOST_USER,
)

SMSService(get_sms_client()).send(
    [user.phone.as_international.replace("+", "00")],
    message,
    settings.SMS_HEADER,
)
```

`EmailService` defaults its client, so `EmailService()` works. `SMSService`
requires one, so pass `get_sms_client()`.

---

## Only email is really asynchronous

This is the thing to know about this package.

| | `send()` | `send_async()` |
|---|---|---|
| `EmailService` | Synchronous SMTP | Genuinely queued, `send_email_task.delay()` |
| `SMSService` | Synchronous HTTP | **Also synchronous.** `send_async` just calls `_send` |

`SMSService.send_async` is a naming convenience, not a queue:

```python
def send_async(self, receivers, message, header, **kwargs) -> bool:
    return self._send(receivers=receivers, message=message, header=header, **kwargs)
```

So an SMS send blocks the request for as long as NetGSM takes to answer. Any
endpoint that sends an SMS inherits that latency, including registration and
password reset. If that matters, wrap it in a Celery task the way email is.

### The email task

```python
@shared_task
def send_email_task(receivers, subject, message, from_email=None, html_message=None):
    ...
```

A module-level `@shared_task`, so a Celery worker must be running for email to go
out in development. Start one with `bin/celery`. Under
`settings/local_test.py`, `CELERY_TASK_ALWAYS_EAGER` makes it run inline, so
tests need no worker. See [../operations/celery.md](../operations/celery.md).

Failures are logged as `send_email_task_failed` and then re-raised, so the task
is recorded as failed rather than silently dropped.

---

## Clients

### `DjangoEmailClient`

Wraps `django.core.mail.send_mail` with `fail_silently=False`, supports
`html_message`, defaults `from_email` to `settings.EMAIL_HOST_USER`, and logs
plus re-raises on failure. Configured by the standard `EMAIL_*` settings, using
Django's SMTP backend.

Note `BaseEmailClient.send_email` declares `receiver_list` while
`DjangoEmailClient.send_email` takes `recipient_list`. The signatures do not
match. Follow the concrete class.

### `NetgsmSMSClient`

Calls `https://api.netgsm.com.tr/sms/send/get/` over `httpx` with
`NETGSM_USER_CODE`, `NETGSM_PASSWORD`, the number, the message, and
`SMS_HEADER`.

NetGSM signals failure with a **200 response whose body is an error code**, so
the client inspects the body:

```python
def is_netgsm_error_code(self, text):
    return text in ["20", "30", "40", "50", "51", "70", "85"]
```

Every send is logged with the number, message, header, and the raw response. Note
that means **message bodies appear in logs**, including password reset codes.

Numbers are normalised from `+90...` to `0090...` before sending.

To use another provider, subclass `BaseSMSClient`, implement `send_sms`, and
change `get_sms_client()`.

---

## Configuration

| Variable | For |
|---|---|
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP |
| `NETGSM_USER_CODE`, `NETGSM_PASSWORD` | NetGSM credentials |
| `SMS_HEADER` | The registered sender name NetGSM requires |
| `CELERY_BROKER_URL` | So `send_email_task` can be queued |

`settings/development.py` supplies placeholder defaults for all of these, so the
app boots without credentials and email fails at send time rather than at import.

---

## Related

- [contact-verification.md](contact-verification.md), the main caller.
- [authy.md](authy.md) for password reset delivery.
- [../operations/celery.md](../operations/celery.md) for the worker.
