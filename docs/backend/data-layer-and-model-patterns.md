# Data Layer and Model Patterns

Conventions for Django models, querysets, and database migrations.

## Migration Policy

### Baseline Migrations

Baseline (initial) migration files **are committed** to the repository. These represent the canonical schema that new environments use to set up their database from scratch. You will find `0001_initial.py` (and occasionally `0002_initial.py` for cross-app dependencies) checked into each app's `migrations/` directory.

### Rules for Subsequent Migrations

1. **Generate migrations locally before running tests.** Always run `python manage.py makemigrations` first; the test suite and CI depend on up-to-date migration files.
2. **Do not commit migrations generated during feature development** unless you are introducing a new model or a schema change that must ship with your PR. Day-to-day generated files are ephemeral and get regenerated in CI.
3. **One migration per logical schema change.** If you need to add a field and backfill data, use two separate migrations: one structural, one data migration.
4. **Name migrations descriptively** when committing them:
   ```bash
   python manage.py makemigrations myapp --name add_status_to_order
   ```
5. **Never edit a migration that has already been applied to production.** Create a new migration instead.
6. **Squash when the chain gets long.** If an app accumulates more than ~10 migrations, consider squashing:
   ```bash
   python manage.py squashmigrations myapp 0001 0010
   ```
7. **Data migrations** use `RunPython` with both a forward and reverse function:
   ```python
   from django.db import migrations

   def populate_status(apps, schema_editor):
       Order = apps.get_model("order", "Order")
       Order.objects.filter(status__isnull=True).update(status="pending")

   def reverse_populate_status(apps, schema_editor):
       pass  # no-op reverse is acceptable for backfills

   class Migration(migrations.Migration):
       dependencies = [("order", "0005_add_status_to_order")]
       operations = [migrations.RunPython(populate_status, reverse_populate_status)]
   ```

### CI Behavior

The GitHub Actions workflow (`.github/workflows/pr_check.yml`) runs `makemigrations` and then the full test suite against a PostgreSQL database. If your model changes require a migration that is missing, CI will fail.
