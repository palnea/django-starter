# Getting started

[Back to docs index](README.md)

---

## The short version

```bash
bin/setup                 # one time
source bin/activate       # every new shell
bin/server                # http://127.0.0.1:8000/
```

`bin/setup` is idempotent. Re-running it on an already-configured machine is
safe, and is usually the fastest way to recover from a broken environment.

---

## Requirements

`bin/setup` installs almost everything. You need to bring:

| | |
|---|---|
| macOS or Debian/Ubuntu | The script branches on these two. Other platforms need the manual path below. |
| Homebrew (macOS) or `apt` (Linux) | Used to install PostgreSQL and Redis. |
| `curl`, `git` | For fetching pyenv and Poetry. |
| Xcode command line tools (macOS) | `xcode-select --install`, if you have never built anything native. |

Everything else, meaning pyenv, Python 3.14.3, PostgreSQL, Poetry 2.3.2, the
virtualenv, the database, and the git hooks, is handled for you.

---

## What `bin/setup` actually does

Fifteen steps, in order. Knowing them makes failures much easier to diagnose,
because the script prints a `[INFO]` line before each one.

| Step | Action |
|---|---|
| 1 | Installs pyenv if missing. |
| 2 | Installs Python 3.14.3 through pyenv and sets it locally. |
| 3 | Installs PostgreSQL, starts the service, resolves the port, and fixes `pg_hba.conf` if local authentication does not work. See [PostgreSQL behaviour](#postgresql-behaviour) below. |
| 4 | Installs Poetry 2.3.2, or warns if your version differs from what CI uses. |
| 5 | Creates a virtualenv at `~/.virtualenvs/myapp` and installs dependencies into it with `POETRY_VIRTUALENVS_CREATE=false`, so Poetry does not make a second hash-named environment. |
| 8 | Creates the `myapp` database and verifies the connection with psycopg2. |
| 9 | Writes a `.env` **only if one does not already exist**. Your existing `.env` is never overwritten. |
| 10 | Creates `media/uploads`, `staticfiles`, and `logs`. |
| 11 | Runs `makemigrations`, `migrate`, `collectstatic`, `compilemessages`. |
| 12 | Offers to create a superuser. Answering `N` is fine, you can do it later. |
| 13 | Copies `scripts/hooks/pre-commit` into `.git/hooks/`. |
| 14 | Runs the test suite with `--keepdb` to validate the setup. |
| 15 | Runs `manage.py check`. |

The step numbering in the script itself skips 6 and 7. That is cosmetic, nothing
is missing.

### PostgreSQL behaviour

This is the part that most often surprises people, so it is worth stating
plainly. The script never assumes a PostgreSQL major version, and it never
assumes port 5432.

| You run | What happens |
|---|---|
| `bin/setup` | Adopts whatever port your running PostgreSQL is already serving on. Nothing global is reconfigured. |
| `DB_PORT=5433 bin/setup` | Requires port 5433. If the running server is on a different port, its `postgresql.conf` is rewritten and the service is restarted. |
| `bin/setup`, with no PostgreSQL installed at all | Installs one and uses `PG_FRESH_INSTALL_PORT`, which defaults to 5432. |

Whichever port it settles on is written into `DATABASE_URL` in your `.env`.

The script also touches `pg_hba.conf`, but only if a local connection does not
already work. If authentication already succeeds, it leaves the file alone.

---

## The `bin/` scripts

Use these rather than raw `manage.py`. They set the settings module, activate
the virtualenv, and apply the flags this project needs.

| Script | Use |
|---|---|
| `bin/setup` | Full environment setup. Idempotent. |
| `source bin/activate` | Enter the virtualenv. Must be sourced, not executed. |
| `bin/server` | Development server on `localhost:8000` with `DEBUG=True`. |
| `bin/server --prod` | Runs `collectstatic`, then serves with `DEBUG=False` under `settings/local_prod.py`. See [why](#catching-static-file-problems-before-deploy). |
| `bin/run-tests` | The whole suite. Accepts paths and flags: `bin/run-tests authy --failfast`. |
| `bin/lint` | Black and Ruff in check mode. |
| `bin/lint --fix` | Black and Ruff in write mode. Run this before committing. |
| `bin/celery` | Starts Redis, a Celery worker, and beat, all in the foreground. Ctrl-C stops everything. |
| `bin/check-translations` | Validates that exception handler strings are marked and translated. |
| `bin/release` | Production release phase: `collectstatic` then `migrate`. Called by the `Procfile`, not by you. |

### Catching static file problems before deploy

Development and production serve static files differently, and the difference is
invisible until you deploy:

- With `DEBUG=True`, Django's finders serve unhashed files straight out of each
  app's `static/` directory. `STATIC_ROOT` is never read, so a stale or missing
  `staticfiles.json` goes unnoticed.
- With `DEBUG=False`, whitenoise serves content-hashed filenames out of
  `STATIC_ROOT` and resolves every `{% static %}` through `staticfiles.json`. A
  missing entry raises `ValueError`.

`bin/server --prod` reproduces the second case locally. Run it before shipping
anything that touches templates or assets.

---

## First run checklist

After `bin/setup` finishes:

```bash
source bin/activate
bin/server
```

Then confirm:

| URL | Expect |
|---|---|
| <http://127.0.0.1:8000/health> | The plain text `ok` |
| <http://127.0.0.1:8000/admin/> | The django-unfold login page |
| <http://127.0.0.1:8000/swagger/> | Swagger UI, after entering the passcode (`swagger` in development) |

If you skipped the superuser step:

```bash
python manage.py createsuperuser
```

---

## The git hook

`bin/setup` installs `scripts/hooks/pre-commit` into `.git/hooks/`. On every
commit it runs `bin/lint` and then `bin/check-translations`, and refuses the
commit if either fails. Merge commits are skipped.

If you cloned and did not run `bin/setup`, install it by hand:

```bash
cp scripts/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## Environment variables

`bin/setup` writes a working development `.env` for you. To see the full set of
variables the project understands, including the ones the setup script does not
write, copy the annotated template:

```bash
cp .env.example .env       # only on a checkout with no .env
```

`.env.example` marks every variable as required or optional and says what it
controls. [operations/settings-and-env.md](operations/settings-and-env.md)
explains how the settings modules consume them.

One thing worth knowing early: `settings/__init__.py` chooses which settings
module to load based on `$ENV`. Unset, it loads `settings/development.py`.

---

## Migrations

Migration files are not committed to this repository. Generate them locally
before running tests or the server:

```bash
python manage.py makemigrations
```

`bin/setup` does this for you on first run. If you pull a branch that changes
models, run it again. CI fails on `makemigrations --check --dry-run` if the
committed models and your migrations disagree.

---

## Troubleshooting

### `bin/setup` cannot connect to PostgreSQL

Check what is actually running and on which port:

```bash
brew services list | grep postgresql      # macOS
pg_isready -p 5432
```

If a server is running on a non-standard port, plain `bin/setup` will adopt it.
If you want to force the standard port, run `DB_PORT=5432 bin/setup`, which
rewrites `postgresql.conf` and restarts the service.

### Virtualenv not found

`bin/server`, `bin/celery`, and `bin/activate` all expect
`~/.virtualenvs/myapp`. If it is missing, run `bin/setup`, which recreates it.

### Poetry installed its own environment

`bin/setup` runs `poetry env remove --all` before creating the virtualenv,
because a stale entry in Poetry's `envs.toml` overrides
`POETRY_VIRTUALENVS_CREATE=false`. If you end up with a hash-named environment
anyway, remove it and re-run setup:

```bash
poetry env remove --all
bin/setup
```

### `ValueError` about a missing staticfiles entry

You are running with `DEBUG=False` and have not collected static files:

```bash
python manage.py collectstatic --noinput
```

`staticfiles/` is generated output and is gitignored. CI and the production
release phase both build it.

### Tests fail immediately with a migration error

Generate migrations first. This is the single most common cause:

```bash
python manage.py makemigrations
bin/run-tests
```

### Celery worker crashes on macOS

Known fork-safety issue. `bin/celery` already works around it by using
`--pool=solo` on Darwin. If you are invoking Celery directly, pass the same flag.

---

## Manual setup

If `bin/setup` does not work on your platform:

```bash
pyenv install 3.14.3 && pyenv local 3.14.3
python -m venv ~/.virtualenvs/myapp
source ~/.virtualenvs/myapp/bin/activate

pip install poetry==2.3.2
POETRY_VIRTUALENVS_CREATE=false poetry install --no-root

createdb myapp
cp .env.example .env       # then set DATABASE_URL

python manage.py makemigrations
python manage.py migrate
python manage.py compilemessages
python manage.py collectstatic --noinput
python manage.py runserver
```

---

Next: [architecture.md](architecture.md), for how a request actually flows
through this codebase.
