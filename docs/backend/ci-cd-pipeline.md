# CI/CD Pipeline

This document describes the continuous integration and continuous delivery pipeline for the Django backend.

---

## Overview

| Aspect | Detail |
|--------|--------|
| Platform | GitHub Actions |
| Trigger | Pull requests to `develop` and `master` |
| Python | 3.14 |
| Package manager | Poetry 2.3.2 |
| Database | PostgreSQL 15 (service container) |
| Formatter | Black |
| Linter | Ruff |
| Test runner | Django `manage.py test` with `--settings=settings.local_test` |

## Pipeline Architecture

```
PR opened / updated
       |
       v
  +---------+
  |  Lint   |  (Black format check, Ruff lint)
  +---------+
       |
       v
  +---------+
  |  Test   |  (PostgreSQL service, migrations, message compilation, Django tests)
  +---------+
       |
       v
  PR status checks pass --> ready for review
```

## Workflow Files

### `pr_check.yml` (existing)

The original workflow that runs on PRs to `develop` and `master`. It contains two jobs:

1. **setup** -- Checks out code, installs Poetry and dependencies, runs Black format check.
2. **run_tests** -- Starts a PostgreSQL 15 service container, installs dependencies, compiles i18n messages, discovers and runs all Django test files.

### `ci.yml` (new)

An enhanced workflow that adds Ruff linting and consolidates the pipeline into two clean jobs:

1. **lint** -- Runs Black (format check) and Ruff (lint check) in a single job to catch style and code-quality issues early.
2. **test** -- Provisions a PostgreSQL 15 service, generates migrations, compiles messages, and runs the full Django test suite.

## Jobs in Detail

### Lint Job

| Step | Command | Purpose |
|------|---------|---------|
| Black check | `poetry run black --check .` | Enforce consistent formatting |
| Ruff check | `poetry run ruff check .` | Catch lint errors, unused imports, common bugs |

### Test Job

| Step | Command | Purpose |
|------|---------|---------|
| Install gettext | `apt-get install -y gettext` | Required for Django message compilation |
| Compile messages | `poetry run python manage.py compilemessages` | Compile i18n `.po` files |
| Make migrations | `poetry run python manage.py makemigrations` | Generate migration files for test DB |
| Run tests | `poetry run python manage.py test --settings=settings.local_test` | Execute full test suite against PostgreSQL |

The test job uses a PostgreSQL 15 service container with:
- User: `postgres`
- Password: `postgres`
- Database: `test_db`
- Exposed on: `localhost:5432`

## Local Quality Gate

Before pushing a PR, developers should run the same checks locally:

```bash
# 1. Format code
black .

# 2. Lint code (if ruff is installed)
ruff check .

# 3. Generate migrations and run tests
python manage.py makemigrations
python manage.py test --settings=settings.local_test
```

## Environment Variables

The CI pipeline sets the following environment variables for the test job:

| Variable | Value | Purpose |
|----------|-------|---------|
| `DATABASE_URL` | `postgres://postgres:postgres@localhost:5432/test_db` | Connect Django to the PostgreSQL service |

All other settings come from `settings/local_test.py`, which is designed to run without external services.

## Adding New Checks

To add a new CI step:

1. Edit `.github/workflows/ci.yml`.
2. Add the step to the appropriate job (`lint` for static analysis, `test` for runtime checks).
3. If the step needs a system package, add it to the `Install system dependencies` step in the test job.
4. Test locally before pushing.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Black check fails | Unformatted code | Run `black .` locally and commit |
| Ruff check fails | Lint violations | Run `ruff check . --fix` locally and commit |
| Migration errors | Model changes without migration | Run `python manage.py makemigrations` locally (do not commit migration files) |
| Test DB connection refused | PostgreSQL service not ready | The workflow uses health checks; if flaky, increase `health-retries` |
| `compilemessages` fails | Missing gettext | Ensure the `Install gettext` step runs before compilation |
