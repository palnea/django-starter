# user

[Back to docs index](../README.md)

Owns the `User` model, which is `AUTH_USER_MODEL`, and the endpoints for reading
and editing users. Authentication flows live in [authy.md](authy.md).

---

## One model, not two

`User` combines authentication and profile in a single model:

```python
class User(AbstractBaseUser, SoftDeleteModel, PermissionsMixin):
```

There is no separate profile model to keep in sync, and no signal wiring one to
the other. Add profile fields directly to `User`.

| Field | Notes |
|---|---|
| `id` | `UUIDField`, primary key, `default=uuid.uuid4`, not editable |
| `email` | Nullable, unique. **This is `USERNAME_FIELD`** |
| `email_verified` | Set by `contact_verification`, or by social login |
| `phone` | `PhoneNumberField`, nullable |
| `phone_verified` | Set by `contact_verification` |
| `fullname` | Profile |
| `locale` | FK to `common.Locale`, defaulted on save |
| `creation_type` | `PERSONAL`, `BUSINESS`, or `INTERNAL` |
| `is_active`, `is_staff` | Standard. `is_superuser` and groups come from `PermissionsMixin` |
| `created`, `updated`, `deleted_at` | `DateTimeWithoutTZField` |

`REQUIRED_FIELDS` is empty, so `createsuperuser` asks only for email and
password.

### UUID primary keys

`User.id` is a UUID, and every other model in the project uses `BigAutoField`.
Consequences you will meet:

- User ids in URLs are strings. `UserViewSet` sets `lookup_url_kwarg = "user_id"`
  and `lookup_field = "id"`, and the route is `<str:user_id>`.
- Ownership comparisons are done as strings, `str(obj.id) == str(request.user.id)`,
  because one side may be a `UUID` and the other a `str`.
- In tests, `create_user` passes `id=uuid.uuid4()` explicitly.

### Constraints

```python
UniqueConstraint(fields=["phone"], condition=deleted_at IS NULL AND phone IS NOT NULL AND phone != "")
UniqueConstraint(fields=["email"], condition=deleted_at IS NULL AND email IS NOT NULL AND email != "")
CheckConstraint(check=email is set OR phone is set, name="user_at_least_email_or_phone_not_null")
```

Two things follow. **A user must have an email or a phone**, enforced by the
database, which is why registration and login both require exactly one of them.
And **uniqueness only applies to live rows**, so soft-deleting a user frees their
email and phone for reuse.

Note `email` also carries `unique=True` on the field itself, in addition to the
partial constraint. The field-level index is unconditional.

### Locale defaults itself

```python
def save(self, *args, **kwargs):
    if self.locale_id is None:
        self.locale = Locale.get_default()
    super().save(*args, **kwargs)
```

Every user always has a locale, which is what
`authenticate_response` relies on when it puts `locale_code` in the access token.

---

## Soft delete

`User` extends `SoftDeleteModel`, so `DELETE /user/<id>/` sets `deleted_at`
rather than removing the row. `CustomUserManager` extends `SoftDeleteManager`, so
`User.objects` excludes deleted rows by default.

`UserViewSet.destroy` catches `Http404` and still reports success:

```python
def destroy(self, request, *args, **kwargs):
    try:
        super().destroy(request, *args, **kwargs)
        view_response = ViewResponseNoContent(response_message=_("Deleted successfully!"))
    except Http404:
        view_response = ViewResponseNoContent(response_message=_("Deleted successfully!"))
    return view_response.rest_response
```

Deleting twice is a success both times, which is what a client retrying a delete
should see.

---

## Subscription helpers

Defined on `User`, used across the payment apps:

| Member | Returns |
|---|---|
| `active_subscription` | The newest subscription whose status counts as active, meaning `trial`, `active`, or `canceled`. A `cached_property` |
| `last_or_active_subscription` | The active one if there is one, otherwise the most recently created. Used to embed subscription state in the access token |
| `has_active_subscription` | `active_subscription is not None` |

Both are `cached_property`, so within one request they are computed once. If you
change subscription state and then read them on the same instance, you get the
stale value. Re-fetch the user.

See [payments-and-subscriptions.md](payments-and-subscriptions.md).

---

## Endpoints

| Method | Path | URL name | Action |
|---|---|---|---|
| `GET` | `/user/` | `user:user-viewset` | List |
| `GET` | `/user/<user_id>/` | `user:user-detail-viewset` | Retrieve |
| `PATCH` | `/user/<user_id>/` | `user:user-detail-viewset` | Partial update |
| `DELETE` | `/user/<user_id>/` | `user:user-detail-viewset` | Soft delete |

There is no create endpoint. Users are created through `/auth/register` or social
login.

```python
class UserViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwner)]
    pagination_class = CustomPageNumberPagination
```

So a user holding `user.view_user` sees everyone, and a user without it sees only
themselves. See [../conventions/permissions.md](../conventions/permissions.md).

### The `User` model is special-cased in ownership

Both `OwnershipFilterMixin` and `IsOwner` special-case it, because `User` has no
`user_id` field. They compare `obj.id` against `request.user.id` instead.
`UserIDInjectionMixin` also skips injection for `User`. If you rename the model,
those three checks look for the literal string `"User"`.

### List filtering

`UserViewSet.get_queryset()` starts from the ownership-filtered queryset and adds
query parameters: `created_from`, `created_to`, `reference_code` (comma
separated), and `order_by`. Default ordering is `-created`.

### Two serializers

```python
def get_serializer_class(self):
    if self.action == "partial_update":
        return UserPartialUpdateSerializer
    return UserSerializer
```

`UserSerializer` exposes `fields = "__all__"` with `password` write-only.
`UserPartialUpdateSerializer` exposes **only `fullname`**.

That narrowness is the defence against a user patching `is_staff` onto themselves.
Widening it is a security change. See
[../conventions/serializers.md](../conventions/serializers.md).

---

## Creating users in code

`User.create_with_password(data)` is the normal path. It validates through
`UserValidator`, requires email or phone plus a password, sets
`creation_type=PERSONAL`, and hashes the password.

`CustomUserManager` also offers `create_user`, `create_superuser`,
`create_user_with_password`, `create_admin`, and
`create_user_with_default_password`.

> **`create_user_with_default_password` is broken.** It falls back to
> `settings.DEFAULT_USER_KEY`, which is not defined anywhere in `settings/`.
> Calling it without a password raises `AttributeError`. Nothing in the codebase
> calls it. Either define the setting or delete the method.

---

## Admin

`user/admin.py` registers `UserAdmin`, combining `unfold.admin.ModelAdmin` with
Django's `BaseUserAdmin`, grouped into Personal info, Verification, Permissions,
Important dates, and Other. Sign in at `/admin/` with email and password.

---

## Related

- [authy.md](authy.md) for registration, login, and tokens.
- [contact-verification.md](contact-verification.md) for how the verified flags get set.
- [../conventions/permissions.md](../conventions/permissions.md) for the ownership special cases.
- [payments-and-subscriptions.md](payments-and-subscriptions.md) for the subscription helpers.
