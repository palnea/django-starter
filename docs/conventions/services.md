# Services

[Back to docs index](../README.md)

Business logic lives in `{app}/services.py`. Views call services. Services touch
models. Nothing in the chain goes backwards.

---

## The pattern

```python
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from common.custom_exceptions.custom_exception import CustomException
from user.models import User


class UserService:
    @staticmethod
    @transaction.atomic
    def deactivate(user_id: str) -> User:
        user = User.objects.get(id=user_id)
        if not user.is_active:
            raise CustomException.business_logic_error(
                title=_("Already Inactive"),
                detail=_("User is already deactivated."),
            )
        user.is_active = False
        user.save()
        return user
```

---

## Rules

### Every method is a `@staticmethod`

Services are namespaces, not objects. They are never instantiated and hold no
state. Every service method in this codebase is a static method, without
exception.

If you find yourself wanting instance state, you probably want a strategy class
instead. `payment/subscription/strategies.py` is the example: `MobilePurchaseStrategy`
is a real object with `__init__`, subclassed per store. It is not a service, and
it does not live in `services.py`.

### Wrap in `@transaction.atomic` when you write more than one row

Decorator order matters. `@staticmethod` goes outermost:

```python
@staticmethod
@transaction.atomic
def register(data, language_code: str = "en", user=None):
    ...
```

Reversed, you get a `TypeError` on the first call. Six of the service methods in
this repository use this pair. Copy the order from them.

### Raise `CustomException`, never a raw DRF exception

```python
raise CustomException.not_found_error(
    title=_("Content not found!"),
    detail=_("User not found"),
)
```

The global exception handler turns that into a structured RFC 7807 response
automatically. Raising `rest_framework.exceptions.NotFound` instead still
produces a valid envelope, because the handler covers `APIException` too, but you
lose control over the title, detail, and error code. See [errors.md](errors.md)
for all nine factory methods.

### Do not log inside services

There are no `log.*` calls in the service layer, and there should not be. Views
log automatically through `LoggingMixin`, and the exception handler logs every
error it renders. A service that logs produces a duplicate line for the same
event. See [logging-and-context.md](logging-and-context.md).

The store webhook notification handlers under `vendor/` are the exception. They
run outside the view logging path, so they log for themselves.

### Return data, not responses

A service returns a model instance, a dict, or `None`. Wrapping the result in a
`ViewResponse` is the view's job. A service that imports from
`common.response.view_response` is reaching into the wrong layer.

### Wrap user-facing strings in `gettext_lazy`

Every `title` and `detail` that can reach a client must be translatable:

```python
from django.utils.translation import gettext_lazy as _
```

See [i18n.md](i18n.md).

---

## Where each layer stops

| Layer | Does | Does not |
|---|---|---|
| View | Validates input via a serializer, calls a service, wraps the result | Contain business rules, query models directly, log by hand |
| Serializer | Shape and field validation, type coercion | Enforce business rules, hit external services |
| Service | Business rules, orchestration, transactions | Build responses, log, know about HTTP |
| Model | Persistence, model-level invariants, managers | Know about requests or responses |

The line between serializer validation and service logic is the one people get
wrong most often. A useful test: if the rule could be checked without touching
the database, it is probably serializer validation. If it depends on the current
state of other rows, it belongs in the service.

---

## Services in this codebase

| Service | Lives in | Does |
|---|---|---|
| `RegistrationService` | `authy` | Creates a user and issues tokens, atomically |
| `PasswordService` | `authy` | Password reset flow |
| `UserService` | `user` | User field updates |
| `ContactVerificationService` | `contact_verification` | Issues and checks verification codes |
| `CodeVerificationService` | `contact_verification` | Verifies email and phone codes |
| `PaymentService` | `payment` | Dispatches a receipt to the right store strategy, checks active subscriptions |
| `TranslationService` | `common` | Bulk translation creation |
| `TranslatedFileService` | `common` | Bulk translated-file creation |

Communication has its own shape. `communications/services/communication_services.py`
holds `EmailService` and `SMSService`, which *are* instantiated with a client.
They are adapters over an external system rather than business logic. See
[../apps/communications.md](../apps/communications.md).

---

## Related

- [views.md](views.md) for how a service result becomes a response.
- [errors.md](errors.md) for the exception factories.
- [serializers.md](serializers.md) for the validation boundary.
