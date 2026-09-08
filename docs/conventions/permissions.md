# Permissions

[Back to docs index](../README.md)

Access control here is built entirely on Django's permission system plus
object-level ownership. There are no role checks anywhere, and adding one would
be a step backwards.

Source: `common/permissions/generic_permissions.py`, `common/view_mixins.py`.

---

## The default

```python
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
```

Everything requires authentication unless a view says otherwise. Opening an
endpoint up is an explicit act.

---

## The common case

Admin or owner, which covers most viewsets:

```python
from common.permissions.generic_permissions import (
    ShortCircuitOr, ActionAwareModelPermissions, IsOwner,
)
from common.view_mixins import OwnershipMixin


class WidgetViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwner)]
    queryset = Widget.objects.all()
```

That reads: a user holding the Django model permission gets through, and anyone
else gets through only for their own rows.

---

## The permission classes

### `ActionAwareModelPermissions`

`DjangoModelPermissions` with two changes.

**It requires `view_*` on GET.** Stock `DjangoModelPermissions` maps `GET` to an
empty list, meaning any authenticated user can read. This class maps it properly:

| Method | Required |
|---|---|
| `GET` | `{app_label}.view_{model}` |
| `POST` | `{app_label}.add_{model}` |
| `PUT`, `PATCH` | `{app_label}.change_{model}` |
| `DELETE` | `{app_label}.delete_{model}` |

**Custom actions get their own permission.** Standard CRUD actions (`list`,
`create`, `retrieve`, `update`, `partial_update`, `destroy`) use the table above.
Anything else requires `{app_label}.{view_name}_{action}`, where `view_name` is
the class name with `ViewSet` stripped and lowercased:

| ViewSet | Action | Permission |
|---|---|---|
| `UserViewSet` | `reset_password` | `user.user_reset_password` |
| `UserViewSet` | `promote_to_admin` | `user.user_promote_to_admin` |

This is the security point. Without it, a custom `POST` action would inherit
`add_widget` and a user allowed to create widgets could invoke any custom action
you later add. Use `get_action_permission_name()` rather than hand-writing these
strings.

At the object level, this class grants access if the user holds the required
model permission, and otherwise returns `False` so composition can defer to an
ownership check.

### `IsOwner`

A pure ownership check with no side effects, which makes it safe to compose.

| Action | Behaviour |
|---|---|
| `list` | Rejects attempts to filter by someone else's id. Scans query parameters for `user_id`, `user`, `owner`, `created_by` and similar, and fails if any names a different user. |
| `create` | Rejects a body that sets `user_id`, `owner_id`, `created_by`, `author_id` or similar to another user. |
| anything else | Returns `True`, deferring to the object-level check. |

At the object level:

- Staff and superusers pass unconditionally. This matters under
  `ShortCircuitOr`: an admin may clear `has_permission` through
  `ActionAwareModelPermissions` but still be evaluated by `IsOwner` at the object
  level, and without the bypass an admin lacking one specific model permission
  would be wrongly blocked.
- For the `User` model, it compares `obj.id` against `request.user.id`.
- For everything else, it compares `obj.user_id`. An object with no `user_id`
  attribute fails closed.

### `IsReadonly`

Allows only `SAFE_METHODS`. Useful for public catalogue endpoints:

```python
permission_classes = [IsReadonly | ActionAwareModelPermissions]
```

### `IsActionPermissionGranted`

Checks `{app_label}.{view_name}_{action}` directly, reading the permission set
from the request-scoped global context rather than querying per call. Use it when
you want action permissions without the model-permission behaviour of
`ActionAwareModelPermissions`.

---

## Composing permissions

### `ShortCircuitOr`, not `|`

```python
permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwner)]
```

DRF's `|` evaluates both operands. `ShortCircuitOr` stops at the first pass. That
matters whenever a permission class does anything besides answer the question,
and it is why this exists: an earlier version of `IsOwner` mutated request data
as a side effect, and `|` triggered it even when the check was unnecessary.

The side effects are now gone, replaced by the explicit mixins below, but
`ShortCircuitOr` remains the right default. It is cheaper and it cannot surprise
you.

Note it is called, not merely listed. `ShortCircuitOr(...)` returns a factory
that DRF instantiates.

### `ConditionalPermission`

Different permissions under different runtime conditions:

```python
permission_classes = [ConditionalPermission({
    lambda r, v: r.user.has_perm("user.view_user"): ActionAwareModelPermissions,
    lambda r, v: True: IsOwner,   # default case, keep it last
})]
```

Conditions are tried in insertion order, and the first match wins. Dictionaries
preserve insertion order, so the catch-all must come last.

---

## The mixins

Permission classes answer yes or no. The mixins do the filtering and injection
that used to hide inside permission classes.

### `OwnershipFilterMixin`

Filters the queryset for `list`, and deliberately does not filter for
`retrieve`, `update`, `partial_update`, or `destroy`.

That asymmetry is the whole design:

- **List** is filtered, so a user simply does not see other people's rows.
- **Object actions** run against the unfiltered queryset, so DRF finds the object
  and then rejects it through `has_object_permission`. That produces a **403**.

If object actions were filtered too, a user requesting someone else's object
would get a **404**, because the row would not be in the queryset at all. Both
are defensible. This codebase chose 403, and the tests assert it. Do not "fix"
this by filtering everywhere.

The permission it checks defaults to `{app_label}.view_{model_name}`, and can be
overridden with `ownership_permission`. The field defaults to `user_id`, and can
be overridden with `ownership_field`. The `User` model is special-cased to filter
on `id`.

### `UserIDInjectionMixin`

On create, if the user holds `{app_label}.add_{model}` they may set any
`user_id`. If they do not, `user_id` is forced to their own:

```python
serializer.save(user_id=self.request.user.id)
```

So clients never need to send `user_id`, and cannot forge it.

### `OwnershipMixin`

`LoggingMixin` + `OwnershipFilterMixin` + `UserIDInjectionMixin`. This is what
you usually want:

```python
class WidgetViewSet(OwnershipMixin, ModelViewSet):
    permission_classes = [ShortCircuitOr(ActionAwareModelPermissions, IsOwner)]
```

It brings automatic view-response logging with it. See [views.md](views.md).

---

## Custom action decorators

For `@action` methods that need an ownership check outside the class-based flow:

```python
from rest_framework.decorators import action
from common.permissions.generic_permissions import check_ownership, require_ownership


@action(detail=True, methods=["post"])
@check_ownership()
def reset_password(self, request, pk=None):
    ...


@action(detail=True, methods=["post"])
@require_ownership()
def activate(self, request, pk=None):
    ...
```

| Decorator | Does |
|---|---|
| `check_ownership(ownership_field="user_id", allow_admin=True, check_query_params=True, check_request_data=True)` | Checks query parameters and body for other users' ids, then object ownership if there is a `pk`. |
| `require_ownership(ownership_field="user_id", allow_admin=True)` | Object ownership only. Detail actions only, and returns 400 without a `pk`. |

Both return plain DRF `Response` objects with a `detail` key rather than the
structured error envelope, so their failures do not look like the rest of the
API. Prefer the permission classes where you can.

---

## Recipes

| Goal | Permissions |
|---|---|
| Admin or owner, the usual case | `[ShortCircuitOr(ActionAwareModelPermissions, IsOwner)]` |
| Public read, permissioned write | `[IsReadonly \| ActionAwareModelPermissions]` |
| Any logged-in user | `[IsAuthenticated]` |
| Model permissions only, no ownership | `[ActionAwareModelPermissions]` |
| A third-party webhook | `[AllowAny]`, with signature verification in the handler. See [views.md](views.md) |

---

## Testing

`custom_test/mixins.py` provides `CRUDPermissionTestsMixin`, which covers the
standard matrix: regular users can list and retrieve but not create, update, or
delete, and unauthenticated users are handled per `unauthenticated_read_allowed`.

`custom_test/test_check_permissions.py` is a repo-wide meta-test over the
permission configuration. If you add a viewset with unusual permissions and that
test fails, read it before working around it. See [../testing.md](../testing.md).

---

## Related

- [views.md](views.md) for `OwnershipMixin` and the logging it carries.
- [errors.md](errors.md) for how a 403 is rendered.
- [../apps/user.md](../apps/user.md) for why the `User` model is special-cased.
