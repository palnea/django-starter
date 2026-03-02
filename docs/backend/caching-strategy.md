# Caching Strategy

This document defines caching patterns and guidelines for the Django REST Framework backend.

## Django Cache Framework

### Backend Configuration

Configure the cache backend in environment-specific settings files under `settings/`.

**Development** (`settings/development.py`) -- use the local-memory cache for simplicity:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dev-cache",
    }
}
```

**Production** (`settings/prod.py`) -- use Redis (the same Redis instance already configured for Celery via `CELERY_BROKER_URL`):

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "myapp",
        "TIMEOUT": 300,  # 5-minute default TTL
    }
}
```

> Use a different Redis database number (e.g., `/1`) than the Celery broker (`/0`) to keep task messages and cache entries isolated.

**Test** (`settings/local_test.py`) -- use the dummy cache so tests never depend on cache state:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}
```

### Per-View Caching

Use Django REST Framework-compatible per-view caching for read-heavy, public or semi-public endpoints. Apply the `cache_page` decorator to the `dispatch` method via `method_decorator`:

```python
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

@method_decorator(cache_page(60 * 15), name="dispatch")  # 15 minutes
class SubscriptionPlanViewSet(ModelViewSet):
    """Subscription plans change infrequently -- safe to cache."""
    ...
```

For finer control, cache only specific actions:

```python
class SubscriptionPlanViewSet(ModelViewSet):
    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        ...

    @method_decorator(cache_page(60 * 15))
    def retrieve(self, request, *args, **kwargs):
        ...
```

**Vary by user.** If the response depends on the authenticated user, add `vary_on_headers`:

```python
from django.views.decorators.vary import vary_on_headers

@method_decorator(vary_on_headers("Authorization"), name="dispatch")
@method_decorator(cache_page(60 * 5), name="dispatch")
class UserProfileViewSet(ModelViewSet):
    ...
```

### Low-Level Cache API

Use the low-level API in service methods for expensive computations or external API calls:

```python
from django.core.cache import cache

class SubscriptionService:
    @staticmethod
    def get_active_plans():
        cache_key = "subscription:active_plans"
        plans = cache.get(cache_key)
        if plans is None:
            plans = list(SubscriptionPlan.objects.filter(is_active=True).values())
            cache.set(cache_key, plans, timeout=60 * 30)  # 30 minutes
        return plans
```

**Key naming convention:** Use `{app}:{resource}:{identifier}` format. Examples:

- `subscription:active_plans`
- `user:profile:{user_id}`
- `payment:receipt:{receipt_id}`

**Bulk operations:**

```python
# Set multiple keys
cache.set_many({"key1": "val1", "key2": "val2"}, timeout=300)

# Get multiple keys
results = cache.get_many(["key1", "key2"])

# Delete multiple keys
cache.delete_many(["key1", "key2"])
```

**Atomic increment/decrement** (useful for rate limiting or counters):

```python
cache.set("api:rate_limit:user:abc123", 0, timeout=3600)
cache.incr("api:rate_limit:user:abc123")
```

## HTTP Caching Headers

Control client-side and CDN caching through HTTP response headers. Apply these in views or via middleware.

### Private, Authenticated Responses

Most endpoints in this project require JWT authentication. Mark these as private so proxies and CDNs never store them:

```python
from django.views.decorators.cache import cache_control

@method_decorator(cache_control(private=True, max_age=0, no_store=True), name="dispatch")
class UserViewSet(OwnershipMixin, ModelViewSet):
    ...
```

### Public, Rarely-Changing Responses

For truly public data (e.g., subscription plan catalog):

```python
@method_decorator(cache_control(public=True, max_age=900, s_maxage=1800), name="dispatch")
class PublicPlanListView(ListAPIView):
    ...
```

- `max_age`: seconds the browser may cache the response.
- `s_maxage`: seconds a shared cache (CDN) may cache the response.

### ETag / Last-Modified

For object-level conditional requests, use Django's `ConditionalGetMiddleware` or set headers manually:

```python
from django.utils.http import http_date
from django.middleware.http import ConditionalGetMiddleware

# Add to MIDDLEWARE (after CommonMiddleware) if desired globally:
# "django.middleware.http.ConditionalGetMiddleware",

# Or per-view:
response["Last-Modified"] = http_date(instance.updated_at.timestamp())
response["ETag"] = f'"{instance.pk}-{instance.updated_at.isoformat()}"'
```

## Cache Invalidation

Cache invalidation is the hardest part. Follow these rules:

### Signal-Based Invalidation

Use Django signals to clear cache when the underlying data changes:

```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

@receiver([post_save, post_delete], sender=SubscriptionPlan)
def invalidate_plan_cache(sender, **kwargs):
    cache.delete("subscription:active_plans")
```

### Service-Layer Invalidation

When a service method modifies data, explicitly invalidate related cache keys:

```python
class SubscriptionService:
    @staticmethod
    def update_plan(plan_id, **data):
        plan = SubscriptionPlan.objects.get(id=plan_id)
        for key, value in data.items():
            setattr(plan, key, value)
        plan.save()
        # Invalidate
        cache.delete("subscription:active_plans")
        cache.delete(f"subscription:plan:{plan_id}")
        return plan
```

### Pattern-Based Invalidation

When you need to invalidate a family of keys, use a version prefix:

```python
def get_plan_cache_version():
    version = cache.get("subscription:plans:version")
    if version is None:
        version = 1
        cache.set("subscription:plans:version", version, timeout=None)
    return version

def invalidate_all_plan_caches():
    """Bump version to effectively invalidate all plan-related caches."""
    cache.incr("subscription:plans:version")

# Usage in service:
version = get_plan_cache_version()
cache_key = f"subscription:plans:v{version}:active"
```

### Timeouts as a Safety Net

Always set a `timeout` on every cache key. Even with explicit invalidation, the TTL prevents serving indefinitely stale data if an invalidation path is missed.

## What NOT to Cache

The following must never be cached:

| Data | Reason |
|---|---|
| **Authentication tokens / JWT responses** | Security risk; tokens are short-lived and user-specific |
| **User-specific write responses** (create, update, delete) | Stale data is confusing and dangerous |
| **Payment and receipt data** | Financial accuracy; always read from the database |
| **Contact verification codes / OTPs** | Security sensitive; codes from `contact_verification` must be real-time |
| **Responses containing PII** in shared caches | Use `Cache-Control: private` at minimum |
| **Admin panel pages** | django-unfold admin must always reflect live data |
| **Swagger / ReDoc documentation** | Development tool; caching adds no value and hides updates |

### Rules of Thumb

1. **When in doubt, do not cache.** Correctness beats performance.
2. **Never cache mutable, user-specific data** in a shared (public) cache.
3. **Always set a TTL.** No indefinite caching without an explicit invalidation strategy.
4. **Log cache misses** in development to identify hot paths worth caching.
5. **Measure before optimizing.** Use Django Debug Toolbar or New Relic to find actual bottlenecks before adding cache layers.
