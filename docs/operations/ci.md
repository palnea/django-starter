# CI

[Back to docs index](../README.md)

`.github/workflows/ci.yml`, running on every pull request into `develop` or
`master`.

---

## Two jobs

```
lint  ->  test
```

`test` declares `needs: lint`, so a formatting error stops the run before any
database is started.

### `lint`

Python 3.14 with pre-releases allowed, Poetry 2.3.2, `poetry install --no-root`,
then:

```bash
poetry run black --check .
poetry run ruff check .
```

Reproduce locally, exactly:

```bash
bin/lint          # check only
bin/lint --fix    # fix
```

### `test`

Runs against a `postgres:15` service with a `pg_isready` health check, on
`DATABASE_URL=postgres://postgres:postgres@localhost:5432/test_db`. Five steps,
each of which exists for a reason:

| Step | Why it is there |
|---|---|
| `apt-get install -y gettext` | `compilemessages` needs GNU gettext |
| `python manage.py compilemessages` | `.mo` files are gitignored build output. Without this the translation meta-tests fail |
| `python manage.py makemigrations --check --dry-run` | Migrations are not committed. This fails if the models would produce one |
| `python manage.py collectstatic --noinput` | `staticfiles/` is not committed. Anything running with `DEBUG=False` needs `staticfiles.json` or whitenoise raises |
| the test loop | See below |

### The test loop

```bash
find . -type f -name "test_*.py" -exec dirname {} \; | sort -u > $temp_file
while IFS= read -r dir; do
    poetry run python manage.py test "$dir" --settings=settings.local_test
done < "$temp_file"
```

Every directory containing a `test_*.py`, run as a separate invocation, stopping
at the first failure. `bin/run-tests` is the same logic locally.

Running each directory separately means each gets a fresh test database. It is
slower than one invocation, and it isolates suites from each other.

---

## Reproducing a failure

```bash
bin/lint
python manage.py compilemessages
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
bin/run-tests
```

---

## Common failures

| Failure | Meaning | Fix |
|---|---|---|
| `black --check` | Formatting | `bin/lint --fix` |
| `ruff check` | Lint | `bin/lint --fix`, then fix what remains by hand |
| `makemigrations --check` exits non-zero | Your models would generate a migration | Run `makemigrations` locally and make sure the model change is complete. Do not commit the file |
| `test_exception_translations` | An unmarked or untranslated handler string, or an orphaned marker | [../conventions/i18n.md](../conventions/i18n.md) |
| `test_check_permissions` | A viewset's permissions are incoherent | [../conventions/permissions.md](../conventions/permissions.md) |
| `test_check_global_context_usage` | `GlobalContext` used outside the allowed layers | [../conventions/logging-and-context.md](../conventions/logging-and-context.md) |
| `test_structured_error_responses` | The error envelope changed | [../conventions/errors.md](../conventions/errors.md) |
| `ValueError` about a missing staticfiles entry | A `{% static %}` reference to a file that is not collected | Check the path, run `bin/server --prod` locally |

---

## Notes

- **Python 3.14 with `allow-prereleases: true`.** Pinned to match
  `.python-version` and `runtime.txt`. Change all three together.
- **Poetry is pinned to 2.3.2.** `bin/setup` warns if your local version differs.
- **No coverage gate and no deploy job.** Deployment is separate, see
  [deployment.md](deployment.md).
- **`develop` and `master` only.** A PR into any other branch runs nothing.

---

## Related

- [../testing.md](../testing.md) for the suite itself.
- [../../CONTRIBUTING.md](../../CONTRIBUTING.md) for the pre-commit hook, which
  runs a subset of this locally.
