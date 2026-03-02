# Feature Flag Conventions

## Current State

No feature flag system is deployed. Feature toggles are managed via environment variables or Django settings where needed, with no formal lifecycle or audit trail.

## Recommended Library: django-waffle

[django-waffle](https://waffle.readthedocs.io/) is the recommended library for this project because:

- It integrates natively with Django's ORM and admin (including django-unfold).
- It supports flags, switches, and samples out of the box.
- It stores state in the database, so flags can be toggled without redeployment.
- It has no external service dependency beyond PostgreSQL (already in use).

### Installation

```bash
pip install django-waffle
```

Add to `INSTALLED_APPS` in `settings/base.py` (after `common`):

```python
INSTALLED_APPS = [
    # ...
    "waffle",
    # ...
]
```

Add the middleware in `MIDDLEWARE` (after `AuthenticationMiddleware`):

```python
MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "waffle.middleware.WaffleMiddleware",
    # ...
]
```

Run migrations:

```bash
python manage.py migrate waffle
```

## Flag Types

django-waffle provides three flag types. Use the right one for the job:

| Type     | Use Case                                         | Granularity              | Example                        |
|----------|--------------------------------------------------|--------------------------|--------------------------------|
| **Flag** | Gradual rollout, A/B testing, user-level toggles | Per-user, group, percent | `enable_new_payment_flow`      |
| **Switch** | Global on/off kill switch                       | All-or-nothing           | `maintenance_mode`             |
| **Sample** | Percentage-based random sampling                | Per-request probability  | `enable_experimental_logging`  |

### Usage in Code

**In views / services:**

```python
import waffle

# Flag (user-aware)
if waffle.flag_is_active(request, "enable_new_payment_flow"):
    return NewPaymentService.process(data)
return LegacyPaymentService.process(data)

# Switch (global, no request needed)
if waffle.switch_is_active("maintenance_mode"):
    raise CustomException.client_error(
        title="Maintenance", detail="System is under maintenance."
    )

# Sample (random per-request)
if waffle.sample_is_active("enable_experimental_logging"):
    log.info("experimental_event", data=payload)
```

**In templates (if applicable):**

```html
{% load waffle_tags %}
{% flag "enable_new_ui" %}
  <div>New UI</div>
{% else %}
  <div>Old UI</div>
{% endflag %}
```

**In tests:**

```python
from waffle.testutils import override_flag, override_switch

class PaymentTests(CustomAPITestCase):
    @override_flag("enable_new_payment_flow", active=True)
    def test_new_payment_flow(self):
        # ...

    @override_switch("maintenance_mode", active=True)
    def test_maintenance_mode_blocks_requests(self):
        # ...
```

## Naming Convention

All flag/switch/sample names must follow this pattern:

```
{category}_{descriptive_name}
```

### Categories

| Prefix        | Meaning                                  | Example                            |
|---------------|------------------------------------------|------------------------------------|
| `enable_`     | Feature rollout (new capability)         | `enable_apple_pay_v2`             |
| `disable_`    | Kill switch (disable existing feature)   | `disable_sms_verification`        |
| `experiment_` | A/B test or experiment                   | `experiment_onboarding_flow`      |
| `ops_`        | Operational toggle (maintenance, debug)  | `ops_maintenance_mode`            |
| `migration_`  | Data or code migration toggle            | `migration_new_subscription_model`|

### Rules

- Use `snake_case` exclusively.
- Maximum 50 characters.
- Names must be descriptive enough to understand without documentation lookup.
- Never reuse a name after a flag has been removed.

## Lifecycle

Every feature flag goes through these stages:

```
1. PROPOSED  -->  2. CREATED  -->  3. ACTIVE  -->  4. FULLY ROLLED OUT  -->  5. REMOVED
```

### Stage Details

| Stage             | Action                                                                                 |
|-------------------|----------------------------------------------------------------------------------------|
| **1. Proposed**   | Developer adds flag name to PR description. Team reviews naming and scope.             |
| **2. Created**    | Flag is created in Django admin (or via data migration) with `everyone=None` (off).    |
| **3. Active**     | Flag is gradually enabled: specific users, then groups, then percentage, then everyone.|
| **4. Fully rolled out** | Flag is set to `everyone=True`. All code paths use the new behavior.             |
| **5. Removed**    | Flag reference is removed from code. Flag is deleted from the database.                |

### Rollout Checklist

- [ ] Flag created in admin with `everyone=None`
- [ ] Code deployed behind flag check
- [ ] Enabled for internal/QA users
- [ ] Enabled for 10% of users (if applicable)
- [ ] Monitored for errors in New Relic for 24 hours
- [ ] Enabled for 50%, then 100%
- [ ] Flag set to `everyone=True`
- [ ] Cleanup PR opened (see below)

## Cleanup Policy

Stale flags are technical debt. Follow these rules:

1. **Maximum lifetime:** 30 days after reaching `everyone=True`, the flag must be removed from code.
2. **Cleanup PR:** When a flag reaches full rollout, immediately open a PR that:
   - Removes all `waffle.flag_is_active()` / `waffle.switch_is_active()` checks for that flag.
   - Removes the old code path.
   - Removes test overrides.
   - Adds a data migration to delete the flag from the `waffle_flag` table.
3. **Tracking:** Add a comment in the PR that created the flag linking to the expected cleanup date.
4. **Audit:** Run a quarterly audit by searching the codebase for `waffle.flag_is_active`, `waffle.switch_is_active`, and `waffle.sample_is_active` to find flags that have outlived their intended lifetime.

### Cleanup Data Migration Example

```python
from django.db import migrations

def remove_flag(apps, schema_editor):
    Flag = apps.get_model("waffle", "Flag")
    Flag.objects.filter(name="enable_new_payment_flow").delete()

class Migration(migrations.Migration):
    dependencies = [
        ("waffle", "0005_auto_..."),
        ("payment", "0010_previous"),
    ]
    operations = [
        migrations.RunPython(remove_flag, migrations.RunPython.noop),
    ]
```
