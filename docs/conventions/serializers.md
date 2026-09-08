# Serializers

[Back to docs index](../README.md)

Serializers own shape and field validation. They do not own business rules.

---

## One serializer per action

Views select a serializer from the current DRF action:

```python
def get_serializer_class(self):
    if self.action == "partial_update":
        return UserPartialUpdateSerializer
    return UserSerializer
```

The point is that different actions accept different fields. `UserSerializer`
exposes the whole model, while `UserPartialUpdateSerializer` accepts exactly one
field:

```python
class UserSerializer(serializers.ModelSerializer):
    deleted_at = serializers.DateTimeField(read_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = "__all__"
        extra_kwargs = {"password": {"write_only": True}}


class UserPartialUpdateSerializer(serializers.ModelSerializer):
    fullname = serializers.CharField(required=False, max_length=50)

    class Meta:
        model = User
        fields = ["fullname"]
```

That narrow update serializer is the whole defence against a client patching
`is_staff` onto themselves. Widening a serializer's `fields` is a security
change, not a convenience change. Review it as one.

Where a viewset has only one alternate serializer, falling through to the
attribute is fine:

```python
def get_serializer_class(self):
    if self.action == "verify":
        return VerifyContactSerializer
    return self.serializer_class
```

---

## Raise `CustomException` from `validate()`

Serializers here do not raise `serializers.ValidationError`. They raise
`CustomException.validation_error`, so the error carries a title and typed
field codes:

```python
def validate(self, data):
    email = data.get("email", None)
    phone = data.get("phone", None)

    if not email and not phone:
        raise CustomException.validation_error(
            field_errors={
                "email": [_("Cannot be empty if no phone provided")],
                "phone": [_("Cannot be empty if no email provided")],
            },
            title=_("Contact Information Required"),
        )
    return data
```

DRF's own `ValidationError` still produces a correct envelope, because the
exception handler walks it into the same structure, including nested serializers
and list serializers. You just do not get to choose the title or the codes. Use
`CustomException` when you are writing the check yourself, and let DRF raise its
own for field-level constraints you declared rather than wrote.

For the strongest client contract, pass `FieldErrorCode` members rather than
bare strings:

```python
raise CustomException.validation_error(
    field_errors={"email": [FieldErrorCode.EMAIL_ALREADY_EXISTS]}
)
```

A bare string is accepted and rendered with code `invalid`, which clients cannot
switch on. See [errors.md](errors.md).

---

## `validate()` versus `validate_<field>()`

Both are used here. The rule is ordinary DRF:

- `validate_<field>(self, value)` for a check that needs only that one field.
  `authy/serializers.py` uses `validate_auth_token` and `validate_code` this way.
- `validate(self, attrs)` for a check that spans fields, such as "email or phone,
  but not both".

---

## Write-only and read-only fields

Anything secret is `write_only`:

```python
extra_kwargs = {"password": {"write_only": True}}
```

Anything server-owned is `read_only`, so a client cannot set it:

```python
deleted_at = serializers.DateTimeField(read_only=True, required=False, allow_null=True)
role = serializers.CharField(read_only=True)
```

---

## Serializers with no model

Several serializers exist only to validate an input payload and never save
anything. They stub out the write methods:

```python
class LoginSerializer(serializers.Serializer):
    def create(self, validated_date):
        pass

    def update(self, instance, validated_data):
        pass

    def validate(self, data):
        ...
```

That is deliberate. The view passes `serializer.validated_data` to a service,
and the service does the work.

---

## Bulk endpoints

`common/serializers.py` shows the bulk pattern: an item serializer, plus a
wrapper whose `validate()` returns a list of validated dicts.

```python
class TranslationBulkCreateItemSerializer(serializers.Serializer):
    ...

class TranslationBulkCreateSerializer(serializers.Serializer):
    def validate(self, attrs) -> List[Dict]:
        ...
```

The service then performs one bulk write. See
[../apps/common.md](../apps/common.md).

---

## Validators are a separate thing

`utils/validators.py` defines `BaseValidator`, and `user/validators.py` subclasses
it as `UserValidator`. These are standalone validation objects, used where
validation has to happen outside a serializer, for instance partway through a
service.

They are instantiated with data and expose methods like
`validate_create(raise_exception=True)`, returning `(errors, validated_data)`.
They raise `CustomException` like everything else.

Prefer a serializer when the input arrives over HTTP. Reach for a validator only
when there is no serializer in the path.

---

## Rules

- Validation of shape belongs here. Rules that depend on other rows belong in a
  service. See [services.md](services.md).
- Never widen `fields` without thinking about who can now write what.
- Wrap every message in `gettext_lazy as _`. See [i18n.md](i18n.md).
- Do not call external services from a serializer. That is orchestration, which
  belongs in a service.

---

## Related

- [views.md](views.md) for `get_serializer_class`.
- [errors.md](errors.md) for field error codes and the error envelope.
- [services.md](services.md) for the validation-versus-logic boundary.
