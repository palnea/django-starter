# common

[Back to docs index](../README.md)

Two unrelated things share this app.

1. **The machinery every other app depends on**: the response envelope, exception
   handling, permissions, view mixins, middleware, pagination, throttles.
   Documented under [../conventions/](../conventions/).
2. **A content translation layer**: `Locale`, `Translation`, `TranslatedFile`,
   with CRUD endpoints. Documented here.

If you are looking for `ViewResponse`, `CustomException`, or the permission
classes, you want the conventions section. This page is about the models.

---

## Content translation is not `gettext`

Two translation systems, easy to confuse.

| | `gettext` catalogues | These models |
|---|---|---|
| Translates | The application's own strings | User-managed content |
| Lives in | `locale/*/LC_MESSAGES/*.po` | Database rows |
| Changed by | A developer, then `compilemessages` | An admin, through the API |
| Covered by | [../conventions/i18n.md](../conventions/i18n.md) | This page |

Product titles and descriptions go through `Translation`. Error messages go
through `gettext`.

---

## `Locale`

A language and region, plus formatting preferences.

| Field | Default |
|---|---|
| `name` | unique |
| `code` | `tr-TR`, unique, validated as an IETF language code via `langcodes` |
| `territory` | `TR`, from `pycountry` |
| `date_format`, `time_format` | `DD/MM/YYYY`, `24h` |
| `currency_code`, `charset`, `direction` | `TRY`, `UTF-8`, `ltr` |

`save()` calls `full_clean()`, so an invalid IETF code raises `ValidationError`
on every save, not only through a form.

```python
Locale.get_default()          # tr-TR, created if missing
Locale.get_default_english()  # en-US, created if missing
```

Both use `get_or_create`, so **calling them can write to the database**. `User.save()`
calls `get_default()` when a user has no locale, so the default locale appears on
first user creation.

> Note the default locale is Turkish, while `LANGUAGE_CODE` is `en-us` and
> `GlobalContext.language_code` falls back to `en`. If your product is not
> Turkish-first, change `Locale.get_default` and the `code` default.

---

## `Translation`

One row per text per language, tied together by a self-referencing `root`.

```
Translation(id=1, text="Monthly plan", locale=en, root=1)   <- the root points at itself
Translation(id=2, text="Aylık plan",   locale=tr, root=1)
```

| Field | Notes |
|---|---|
| `text` | 512 characters |
| `root` | FK to self. The group identifier |
| `locale` | FK to `Locale`, defaulted on save |

```python
UniqueConstraint(fields=["root", "locale"], condition=deleted_at IS NULL)
```

One translation per language per group.

### `root` is self-assigned

```python
def save(self, ...):
    is_create = not bool(self.id)
    if self.locale_id is None:
        self.locale = Locale.get_default()
    super().save(...)
    if is_create and self.root_id is None:
        self.root_id = self.id
        self.save()
```

A new row with no `root` becomes its own root, which costs **two INSERT/UPDATE
round trips**. To add a translation to an existing group, set `root` to the
group's root id.

### Deleting a root deletes the group

```python
def delete(self, ...):
    if self.root_id is None or self.root_id == self.id:
        self.translations.exclude(id=self.id).delete()
    super().delete(...)
```

Soft-deleting the root soft-deletes every sibling. Deleting a non-root removes
only that language.

### Reading translated text

```python
translation.get_text_by_locale_code_or_default("tr")
```

Falls back in order: the requested locale, then `en`, then any translation in the
group, then `""`.

For many at once, avoiding the N+1:

```python
Translation.get_list_of_texts_from_id_list([title_id, description_id], language_code)
```

Returns a dict keyed by **both** the root id and the translation id, so a lookup
works whichever id you hold. `BuyableViewSet.retrieve` uses exactly this. See
[payments-and-subscriptions.md](payments-and-subscriptions.md).

For querysets:

```python
Translation.create_prefetch_for_language(language_code, "buyables__title")
```

`TranslationManager` already applies `select_related("root")` to every query.

---

## `TranslatedFile`

The same root-and-locale idea, for files in object storage rather than text.

| Field | Notes |
|---|---|
| `name`, `extension` | Identity |
| `type` | `FileType`: `image`, `audio`, `video` |
| `vendor`, `vendor_url`, `bucket_name` | Defaulted from the cloud storage settings |
| `directory` | Defaults to `TRANSLATED_FILE_DIRECTORY`, `"translated_file/"` |
| `public` | Defaults to `True` |
| `root`, `locale` | As `Translation` |

`TranslatedFileSerializer` exposes `url` and `presigned_url`, the latter via
`IDriveClient.create_presigned_url`. See [cloud-storage.md](cloud-storage.md).

> **Import-time gotcha.** The `vendor_url` field default is
> `get_cloud_storage_client().endpoint`, evaluated **when the module is imported**,
> not per row. So a broken or missing storage configuration breaks importing
> `common.models`, which breaks everything. If Django fails to start with a
> storage error, this is why. Making it a callable, as `bucket_name` and `vendor`
> already are, would fix it.

---

## Endpoints

All under `/common/`, namespaced `common:`.

| Method | Path | Purpose |
|---|---|---|
| `GET`, `POST` | `/common/translation/` | List, create |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/common/translation/<id>/` | Detail |
| `POST` | `/common/translation/bulk_create/` | Many at once |
| `GET`, `POST` | `/common/translated_file/` | List, create |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/common/translated_file/<id>/` | Detail |
| `POST` | `/common/translated_file/bulk_create/` | Many at once |
| `GET`, `POST` | `/common/locale/` | List, create |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/common/locale/<id>/` | Detail |

### Bulk create

The pattern is an item serializer plus a wrapper whose `validate()` returns a
list of validated dicts, which the service then writes in one go:

```
TranslationBulkCreateSerializer.validate()  ->  List[Dict]
        |
TranslationService.bulk_create(request_data, query_params)
```

Use it when seeding a product's title in every language. See
[../conventions/serializers.md](../conventions/serializers.md).

---

## The rest of `common`

Everything below is documented elsewhere. Listed here so you know where it is.

| Path | What | Documented in |
|---|---|---|
| `response/view_response.py` | `ViewResponse` and friends | [views.md](../conventions/views.md) |
| `response/structured_error_response.py` | The RFC 7807 error body | [errors.md](../conventions/errors.md) |
| `response/response_information_codes/` | `ErrorCode`, `FieldErrorCode`, `GeneralErrorCode`, `MessageCode` | [errors.md](../conventions/errors.md) |
| `custom_exceptions/custom_exception.py` | `CustomException` | [errors.md](../conventions/errors.md) |
| `exception_handling/` | The global handler and its mapper | [errors.md](../conventions/errors.md), [i18n.md](../conventions/i18n.md) |
| `permissions/generic_permissions.py` | All permission classes | [permissions.md](../conventions/permissions.md) |
| `view_mixins.py` | `LoggingMixin`, `OwnershipMixin` | [views.md](../conventions/views.md) |
| `middlewares/` | Health check, global context, swagger gate | [architecture.md](../architecture.md) |
| `pagination.py` | `CustomPageNumberPagination`, `?size=`, max 100 | |
| `throttles.py` | `AuthRateThrottle`, the `auth` scope | [authy.md](authy.md) |
| `fields.py` | `DateTimeWithoutTZField`, used across every model | |
| `model_managers/ordered_managers.py` | `ordered_soft_delete_manager_factory`, for reorderable rows | |
| `types.py` | `LocaleCode`, `FileType` | |
| `examples/` | Runnable examples of the error system | [errors.md](../conventions/errors.md) |

### `DateTimeWithoutTZField`

Every timestamp in this project uses it, and `USE_TZ = False`. So datetimes are
naive and stored without a zone, which is why the code uses
`datetime.datetime.utcnow()` rather than `django.utils.timezone.now()`. Mixing
aware and naive datetimes here raises `TypeError`. Follow the surrounding code.

---

## Related

- [../conventions/](../conventions/) for the machinery.
- [cloud-storage.md](cloud-storage.md) for where `TranslatedFile` content lives.
- [../conventions/i18n.md](../conventions/i18n.md) for the other translation system.
