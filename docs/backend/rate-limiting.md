# Rate Limiting

## Current State

No throttle classes are configured globally in `REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]` or `DEFAULT_THROTTLE_RATES` in `settings/base.py`. Throttled requests are handled by the exception handler, which maps DRF's `Throttled` exception to `ErrorCode.THROTTLED` (`ERR_THROTTLED`) with an RFC 7807 error response.

## DRF Throttle Configuration

To enable rate limiting, add the following to `REST_FRAMEWORK` in `settings/base.py`:

```python
REST_FRAMEWORK = {
    # ... existing keys ...
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "300/minute",
        "auth": "10/minute",
        "contact_verification": "5/minute",
    },
}
```

**Cache backend requirement:** DRF throttling uses Django's default cache. Configure a shared cache (Redis recommended, since Redis is already in use for Celery):

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/1"),
    }
}
```

## Rate Limit Tiers

| Tier                    | Scope                    | Rate          | Applies To                              |
|-------------------------|--------------------------|---------------|-----------------------------------------|
| Anonymous               | `anon`                   | 60/min        | Unauthenticated requests                |
| Authenticated (default) | `user`                   | 300/min       | Any authenticated user                  |
| Authentication endpoints| `auth`                   | 10/min        | Login, register, token refresh           |
| Contact verification    | `contact_verification`   | 5/min         | SMS/email verification sends             |
| Social auth             | `auth`                   | 10/min        | Apple/Google/Facebook sign-in            |
| Admin / staff           | (exempt)                 | No limit      | Users with `is_staff=True`              |

## Custom Throttle Classes

### Per-Scope Throttle

Create throttles in `common/throttles.py`:

```python
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Applied to login, register, and token refresh endpoints."""
    scope = "auth"


class ContactVerificationThrottle(UserRateThrottle):
    """Applied to SMS and email verification send endpoints."""
    scope = "contact_verification"


class StaffExemptUserThrottle(UserRateThrottle):
    """Default user throttle that exempts staff users."""
    scope = "user"

    def allow_request(self, request, view):
        if request.user and request.user.is_staff:
            return True
        return super().allow_request(request, view)
```

### Applying Per-View

```python
from common.throttles import AuthRateThrottle

class LoginView(APIView):
    throttle_classes = [AuthRateThrottle]
    # ...
```

## Response Headers

When throttling is active, DRF automatically includes a `Retry-After` header (in seconds) on `429 Too Many Requests` responses. The response body follows the project's standard error envelope:

```json
{
    "type": "throttled",
    "status": 429,
    "title": "Request was throttled.",
    "detail": "Expected available in 42 seconds.",
    "instance": "/api/v1/auth/login/",
    "response_code": "ERR_THROTTLED"
}
```

Key headers on throttled responses:

| Header         | Value                                    |
|----------------|------------------------------------------|
| `Retry-After`  | Seconds until the client may retry       |
| `Content-Type` | `application/json`                       |

## Abuse Prevention

### IP-Based Blocking

For persistent abusers, implement IP blocking at the reverse proxy level (nginx / load balancer) rather than in Django. This avoids consuming application resources.

### Graduated Penalties

For endpoints that are frequent abuse targets (login, registration), consider a burst + sustained strategy:

```python
"DEFAULT_THROTTLE_RATES": {
    "auth_burst": "5/minute",
    "auth_sustained": "30/hour",
}
```

Apply both throttle classes to the same view so that both limits are enforced simultaneously.

### Monitoring Throttle Events

Log throttle hits via New Relic custom events. The exception handler already maps `Throttled` exceptions, so all 429 responses appear in New Relic error tracking. Set up an alert condition:

- **Condition:** `ERR_THROTTLED` count > 100 in 5 minutes
- **Severity:** Warning
- **Action:** Investigate whether the traffic is legitimate load or abuse

### Recommendations

1. **Start conservative** -- deploy with the rates in the table above and monitor for false positives before tightening.
2. **Use Redis cache** -- the in-memory `LocMemCache` does not work across multiple Gunicorn workers; Redis is required for accurate counting.
3. **Exempt health checks** -- the `HealthCheckMiddleware` already short-circuits before DRF, so `/health/` is not throttled.
4. **Document client expectations** -- publish rate limits in API documentation so mobile clients can implement exponential backoff on 429 responses.
