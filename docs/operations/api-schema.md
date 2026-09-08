# API schema and documentation

[Back to docs index](../README.md)

OpenAPI 3 through drf-spectacular, served as Swagger UI and ReDoc, behind a
passcode.

---

## Endpoints

| Path | Serves | URL name |
|---|---|---|
| `/api/schema/` | The raw OpenAPI 3 document | `schema` |
| `/swagger/` | Swagger UI | `schema-swagger-ui` |
| `/redoc/` | ReDoc | `schema-redoc` |

All three are gated. See below.

---

## Configuration

```python
SPECTACULAR_SETTINGS = {
    "TITLE": "MyApp API",
    "VERSION": "v1",
    "DESCRIPTION": "Monolith MyApp API",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {"docExpansion": "list"},
    "APPEND_COMPONENTS": {
        "securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer"}}
    },
    "SECURITY": [{"BearerAuth": []}],
}
```

`SERVE_INCLUDE_SCHEMA: False` keeps the schema endpoint out of the schema itself.
`BearerAuth` means the Authorize button in Swagger UI takes a JWT, so you can
paste an access token and call authenticated endpoints from the browser.

Change `TITLE`, `VERSION`, and `DESCRIPTION` when you rename the project. See
[../starting-a-new-project.md](../starting-a-new-project.md).

---

## The passcode gate

`common/middlewares/swagger_middleware.py` protects all three URLs:

```python
if any(url in request.path for url in protected_urls):
    if not request.session.get("has_swagger_access", False):
        if request.method == "POST" and request.POST.get("passcode") == settings.SWAGGER_ACCESS_PASSCODE:
            request.session["has_swagger_access"] = True
            return redirect(request.path)
        return HttpResponse(passcode_form, status=401)
```

A GET returns a 401 with a small form. Posting the right passcode sets a session
flag and redirects. The form lives in
`common/templates/swagger/passcode.py`.

Two things follow:

- **It is session-based**, so it needs cookies. A scripted client fetching
  `/api/schema/` gets the 401 form, not JSON, unless it carries the session
  cookie.
- **`SWAGGER_ACCESS_PASSCODE` unset means the check compares against `None`**,
  and no submitted value equals `None`, so the docs become unreachable rather
  than public. `settings/development.py` defaults it to `swagger`.

Set a real value in every deployed environment.

---

## Schema caching

```python
API_SCHEMA_CACHE_TIMEOUT = 0 if DEBUG else 3600
```

The schema route wraps `SpectacularAPIView` in `cache_page` and
`cache_control(private=True)`, plus the passcode decorator:

```python
path("api/schema/", swagger_passcode_required(
    cache_control(private=True)(
        cache_page(settings.API_SCHEMA_CACHE_TIMEOUT)(SpectacularAPIView.as_view())
    )
), name="schema"),
```

> **The timeout is computed in `base.py`, from `base.py`'s own `DEBUG`, which is
> `False`.** `settings/development.py` sets `DEBUG = True` afterwards, but the
> constant has already been evaluated. So local development caches the schema for
> an hour, not zero, and a schema change appears stale until the cache expires.
>
> `settings/local_prod.py` documents this and sets the value explicitly. If the
> stale schema bothers you locally, do the same in `development.py`, or clear the
> cache.

---

## Keeping the schema useful

drf-spectacular reads serializers and viewsets. Two things this codebase does:

**Declare the request body** where the view does not use `get_serializer`:

```python
@extend_schema(request=UserLoginSerializer)
def post(self, request):
    ...
```

**Hide endpoints that are not part of the public API**, which is what the store
webhooks do:

```python
@extend_schema(exclude=True)
def create(self, request, *args, **kwargs):
    ...
```

Note the generated schema describes the **unwrapped** serializer output. The
actual body is wrapped in the response envelope, with your payload under
`response_body`. The schema does not currently express that wrapper, so treat
documented response shapes as the contents of `response_body`. See
[../conventions/views.md](../conventions/views.md).

---

## Generating the schema as a file

```bash
python manage.py spectacular --file schema.yml
```

Useful for client generation, and it bypasses both the passcode and the cache.

---

## Related

- [../conventions/views.md](../conventions/views.md) for the response envelope.
- [../conventions/errors.md](../conventions/errors.md) for the error envelope.
- [settings-and-env.md](settings-and-env.md) for `SWAGGER_ACCESS_PASSCODE`.
