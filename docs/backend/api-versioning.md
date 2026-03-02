# API Versioning

## Current State

The project currently has **no API versioning**. All endpoints are served at their base paths without version prefixes:

```
/auth/
/user/
/contact-verification/
/payment/
/common/
```

The Swagger schema declares `default_version="v1"` in its `openapi.Info` metadata, but this is purely informational and does not affect URL routing.

This means any breaking change to an endpoint immediately affects all clients. As the number of API consumers grows (mobile apps, web frontends, third-party integrations), this becomes a significant risk.

## Chosen Approach: URL Prefix Versioning

We will adopt **URL prefix versioning** using Django REST Framework's built-in `URLPathVersioning`.

### Why URL Prefix

| Approach | Pros | Cons |
|---|---|---|
| **URL prefix** (`/api/v1/`) | Explicit, easy to route, cacheable, simple to understand | URLs change between versions |
| Header-based (`Accept: application/vnd.api+json;version=1`) | Clean URLs | Hidden from logs, harder to test, poor browser support |
| Query parameter (`?version=1`) | Easy to add | Caching issues, easy to forget |

URL prefix is the most widely adopted pattern and works well with Django's URL routing, reverse proxies, and API gateways.

### Target URL Structure

```
/api/v1/auth/
/api/v1/user/
/api/v1/contact-verification/
/api/v1/payment/
/api/v1/common/
```

## Breaking vs Non-Breaking Changes

### Non-Breaking Changes (No New Version Required)

These changes are backward-compatible and can be deployed to the current version:

- Adding a new optional field to a request body
- Adding a new field to a response body
- Adding a new endpoint
- Adding a new optional query parameter
- Adding a new enum value (if clients handle unknown values gracefully)
- Relaxing a validation constraint (e.g., increasing max length)
- Improving error messages without changing error codes
- Performance improvements

### Breaking Changes (Require New Version)

These changes are backward-incompatible and require a new API version:

- Removing or renaming a field from a request or response body
- Changing a field's data type (e.g., string to integer)
- Changing a required field to a different name
- Removing an endpoint
- Changing URL path structure
- Changing authentication mechanism
- Changing the response envelope structure
- Making a previously optional field required
- Tightening a validation constraint (e.g., reducing max length)
- Changing error code values or error response structure
- Changing pagination behavior

## Deprecation Policy

### Timeline

1. **Announcement** (Day 0): Deprecation is announced in API changelog and response headers.
2. **Sunset header** (Day 0+): Deprecated version responses include a `Sunset` header with the removal date.
3. **Migration period** (minimum 6 months): Both old and new versions are supported.
4. **Warning phase** (last 2 months): Increase logging of deprecated version usage. Notify known consumers directly.
5. **Removal** (after sunset date): Old version returns `410 Gone`.

### Communication

- Add `Deprecation: true` and `Sunset: <date>` headers to responses from deprecated versions.
- Document deprecation in the API changelog.
- Notify mobile app teams to release updates before the sunset date.
- Monitor usage of deprecated versions via logging.

### Example Sunset Header

```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: Sat, 01 Mar 2027 00:00:00 GMT
Link: </api/v2/user/>; rel="successor-version"
```

## Implementation Guide

### Step 1: Add DRF Versioning Settings

In `settings/base.py`:

```python
REST_FRAMEWORK = {
    # ... existing settings ...
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "VERSION_PARAM": "version",
}
```

### Step 2: Update URL Configuration

In `manage/urls.py`:

```python
from django.urls import path, include

api_v1_patterns = [
    path("auth/", include("authy.urls")),
    path("user/", include("user.urls")),
    path("contact-verification/", include("contact_verification.urls")),
    path("payment/", include("payment.urls")),
    path("common/", include("common.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),

    # Versioned API
    path("api/v1/", include((api_v1_patterns, "v1"))),

    # Keep legacy unversioned routes during migration (temporary)
    path("auth/", include("authy.urls")),
    path("user/", include("user.urls")),
    path("contact-verification/", include("contact_verification.urls")),
    path("payment/", include("payment.urls")),
    path("common/", include("common.urls")),

    # Documentation
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
```

### Step 3: Migrate Clients

1. Deploy with both versioned and unversioned routes active.
2. Update all clients (mobile apps, web frontends) to use `/api/v1/` prefix.
3. Add deprecation logging to unversioned routes.
4. After all clients have migrated, remove unversioned routes.

### Step 4: Adding a New Version (Future)

When a breaking change is needed:

1. Create a new URL pattern set for `v2`.
2. Add `"v2"` to `ALLOWED_VERSIONS`.
3. In views that differ between versions, check `request.version`:

```python
def retrieve(self, request, *args, **kwargs):
    if request.version == "v2":
        serializer_class = UserV2Serializer
    else:
        serializer_class = UserSerializer
    # ...
```

4. Alternatively, create separate view classes per version if changes are substantial.
5. Begin the deprecation policy for `v1`.

### Step 5: Swagger Documentation Per Version

Update the schema view to reflect the active version:

```python
schema_view_v1 = get_schema_view(
    openapi.Info(
        title="MyApp API",
        default_version="v1",
        description="MyApp API v1",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    patterns=api_v1_patterns,
)
```

## Version Lifecycle

```
v1  [active]  -----> [deprecated] -----> [sunset/removed]
v2            [active] -----------------> [deprecated] ---> ...
```

Each version should have a minimum lifespan of 12 months from its release to its sunset date. No more than 2 versions should be actively supported at any time to limit maintenance burden.
