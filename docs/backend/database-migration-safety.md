# Database Migration Safety

This document defines migration policies, safe patterns, and rollback procedures for the PostgreSQL-backed Django project.

## Migration Policy

### Migrations ARE Committed

Migration files are generated locally and **committed to version control**. This ensures:

- Every environment applies the same deterministic schema changes.
- Code review covers schema changes alongside application code.
- CI can detect conflicts between branches that touch the same models.

> **Note:** The CLAUDE.md instruction "Never commit migration files" applies only to Claude Code's automated workflow (to avoid accidental auto-generated commits). Human developers and intentional PRs **must** include migration files.

### Workflow

1. Make model changes in `{app}/models.py`.
2. Generate migrations:
   ```bash
   python manage.py makemigrations
   ```
3. Review the generated file in `{app}/migrations/`. Verify it does what you expect.
4. Run migrations locally:
   ```bash
   python manage.py migrate
   ```
5. Run the test suite:
   ```bash
   python manage.py test --settings=settings.local_test
   ```
6. Commit the migration file alongside the model changes in the same PR.

### Naming Conventions

Django auto-generates names like `0003_auto_20260302_1234.py`. For clarity, rename with a descriptive suffix:

```bash
python manage.py makemigrations --name add_expires_at_to_subscription
```

This produces `0003_add_expires_at_to_subscription.py`, which is immediately understandable in code review and git history.

## Safe Migration Patterns

### Adding a Column

**Safe by default** as long as the column is nullable or has a default value. Adding a non-nullable column without a default will lock the table and fail on existing rows.

```python
# SAFE: nullable column
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="subscription",
            name="expires_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
```

```python
# SAFE: column with a database-level default
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="subscription",
            name="is_trial",
            field=models.BooleanField(default=False),
        ),
    ]
```

```python
# DANGEROUS: non-nullable without default -- Django will prompt for a default
# at makemigrations time. Provide one or make the field nullable first.
```

**Pattern for required fields on existing tables:**

1. Add the column as nullable (`null=True`).
2. Deploy and backfill data (see Data Migrations below).
3. In a subsequent migration, remove `null=True` and set a default or make it required.

### Removing a Column

Removing a column is a **two-phase** operation to avoid downtime:

**Phase 1 -- Stop using the column:**

1. Remove all references to the field in application code (serializers, views, services, filters).
2. Deploy this change. The column still exists in the database but is no longer read or written.

**Phase 2 -- Drop the column:**

1. Remove the field from the model.
2. Generate and commit the migration.
3. Deploy.

This prevents errors when old application instances (during a rolling deploy) try to SELECT or INSERT the removed column.

### Renaming a Column

**Never rename a column directly in production.** The `RenameField` operation issues `ALTER TABLE ... RENAME COLUMN`, which will break any running application code that references the old name.

**Safe rename pattern (three-phase):**

1. **Add the new column** (nullable). Deploy a migration that copies data from old to new.
2. **Dual-write.** Update application code to write to both columns, read from the new one. Deploy.
3. **Drop the old column.** Remove old-column references and deploy the removal migration.

```python
# Phase 1 migration: add new column + copy data
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="user",
            name="display_name",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.RunSQL(
            sql='UPDATE "user_user" SET "display_name" = "name"',
            reverse_sql='UPDATE "user_user" SET "name" = "display_name"',
        ),
    ]
```

### Adding an Index

Adding an index on a large table locks the table for the duration of the `CREATE INDEX` operation. Use `CONCURRENTLY`:

```python
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # Required for CONCURRENTLY

    operations = [
        AddIndexConcurrently(
            model_name="payment",
            index=models.Index(fields=["created_at"], name="payment_created_at_idx"),
        ),
    ]
```

> Set `atomic = False` on the migration class. Concurrent index creation cannot run inside a transaction.

### Changing a Column Type

Changing a column type (e.g., `CharField` to `TextField`, or changing `max_length`) can require a full table rewrite. Evaluate the impact:

- `CharField(max_length=100)` to `CharField(max_length=255)`: Safe on PostgreSQL (no rewrite needed for varchar expansion).
- `IntegerField` to `CharField`: Dangerous; requires a rewrite. Use the add-copy-drop pattern instead.

## Data Migrations

Use data migrations for backfilling, transforming, or seeding data. Create them with:

```bash
python manage.py makemigrations --empty {app_name} --name backfill_display_name
```

### Structure

```python
from django.db import migrations

def backfill_display_name(apps, schema_editor):
    User = apps.get_model("user", "User")
    batch_size = 1000
    users = User.objects.filter(display_name__isnull=True)

    while True:
        batch = list(users[:batch_size])
        if not batch:
            break
        for user in batch:
            user.display_name = user.first_name or user.email
        User.objects.bulk_update(batch, ["display_name"], batch_size=batch_size)

def reverse_backfill(apps, schema_editor):
    # Provide a reverse operation or use migrations.RunPython.noop
    pass

class Migration(migrations.Migration):
    dependencies = [
        ("user", "0003_add_display_name"),
    ]
    operations = [
        migrations.RunPython(backfill_display_name, reverse_backfill),
    ]
```

### Data Migration Rules

1. **Always use `apps.get_model()`** -- never import models directly. Direct imports use the current model state, not the state at migration time.
2. **Process in batches** to avoid memory issues and long-running transactions on large tables.
3. **Always provide a reverse function** (or explicitly use `migrations.RunPython.noop`) so `migrate --reverse` works.
4. **Keep data migrations separate** from schema migrations. One migration file per concern.
5. **Do not call service methods or custom model managers** in migrations. They may depend on fields or code that does not exist at that migration point.

## Rollback Procedures

### Rolling Back a Migration

```bash
# Roll back the last migration for an app
python manage.py migrate {app_name} {previous_migration_number}

# Example: roll back user app to migration 0002
python manage.py migrate user 0002
```

### When Rollback Is Safe

- The migration only added a nullable column (rollback drops it).
- The migration only added an index (rollback drops it).
- The migration is a data migration with a proper reverse function.

### When Rollback Is Dangerous

- The migration dropped a column -- data is already lost; rollback recreates an empty column.
- The migration performed an irreversible data transformation.
- Other migrations depend on this one (check `dependencies` in later migration files).

### Rollback Checklist

1. Identify the migration to roll back: `python manage.py showmigrations {app_name}`.
2. Check if the migration is reversible: read the migration file for `RunPython.noop` reverse operations or `RunSQL` without `reverse_sql`.
3. If irreversible, plan a forward-fix migration instead of rolling back.
4. Roll back in staging first. Verify application behavior.
5. Roll back in production. Monitor logs and error rates.

### Forward-Fix vs. Rollback

Prefer a **forward-fix** (a new migration that corrects the problem) over a rollback when:

- The migration has been applied for more than a few minutes and other data changes have occurred.
- The migration is irreversible.
- Rolling back would cause data loss.

## CI Integration

The GitHub Actions workflow (`.github/workflows/pr_check.yml`) validates migrations on every pull request.

### What CI Checks

1. **Migration generation**: CI runs `makemigrations` to verify no migrations are missing. If a model change is present without a corresponding migration file, the test run fails.
2. **Migration application**: The test runner applies all migrations to a fresh PostgreSQL database before running tests.
3. **Test suite**: All tests in `{app}/test/` directories run against the migrated schema.

### Detecting Missing Migrations

Add an explicit check to CI to catch uncommitted migrations:

```bash
python manage.py makemigrations --check --dry-run
```

This exits with code 1 if any model changes lack a corresponding migration file. Consider adding this as a dedicated CI step.

### Detecting Migration Conflicts

When two branches add migrations to the same app, Django detects the conflict at `migrate` time. To resolve:

1. Merge the target branch into your branch.
2. Run `python manage.py makemigrations --merge` to create a merge migration.
3. Commit the merge migration.

### Pre-Merge Checklist

Before merging a PR that includes migrations:

- [ ] Migration file is committed and reviewed.
- [ ] Migration is named descriptively (`--name` flag).
- [ ] Schema changes are backwards-compatible (or a multi-phase plan is documented).
- [ ] Data migrations process in batches and have reverse functions.
- [ ] `python manage.py makemigrations --check --dry-run` passes (no missing migrations).
- [ ] Tests pass with `--settings=settings.local_test`.
- [ ] Large table operations use `AddIndexConcurrently` or equivalent.
- [ ] Rollback plan is documented in the PR description for non-trivial changes.
