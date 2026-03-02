# Dependency Management Policy

## Overview

This project uses [Poetry](https://python-poetry.org/) for dependency management. Dependencies are declared in `pyproject.toml` and resolved into `requirements.txt` for deployment.

## Lock File Policy

### Current State

The `poetry.lock` file is listed in `.gitignore` and is **not** committed to version control. This is a known gap.

### Recommended Policy

**Commit `poetry.lock` to version control.** This ensures:

- Reproducible builds across all environments (dev, CI, staging, production).
- Protection against unexpected transitive dependency updates.
- Visibility into exactly which versions are deployed.

To implement this change:

1. Remove the `poetry.lock` line from `.gitignore`.
2. Run `poetry lock` to generate a fresh lock file.
3. Commit `poetry.lock`.
4. Update CI to use `poetry install --no-root` (which respects the lock file) instead of installing from `requirements.txt`.

### Requirements.txt

The `requirements.txt` file is generated from Poetry's lock resolution and is used for deployment environments that do not have Poetry installed. It should be regenerated whenever dependencies change:

```bash
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

## Dependency Groups

Organize dependencies into logical groups in `pyproject.toml`:

### Current Structure

All dependencies are in `[tool.poetry.dependencies]` with no separation between production and development/test dependencies.

### Recommended Structure

```toml
[tool.poetry.dependencies]
# Production dependencies only
python = "^3.14"
Django = "^5.2"
djangorestframework = "^3.16.0"
# ... other runtime dependencies

[tool.poetry.group.dev.dependencies]
# Development and testing tools
black = "^25.1.0"
model-bakery = "^1.20.4"

[tool.poetry.group.test.dependencies]
# Test-only dependencies (if any beyond dev)
```

Dependencies like `black` and `model-bakery` are development/test tools and should not be installed in production.

## Adding a New Dependency

### Process

1. **Evaluate the dependency:**
   - Is it actively maintained? Check last commit date and release frequency.
   - Does it have a permissive license compatible with our project?
   - How many transitive dependencies does it pull in?
   - Are there lighter alternatives?
   - Does it have known security vulnerabilities? Check via `pip-audit` or GitHub advisory database.

2. **Add the dependency:**
   ```bash
   # Production dependency
   poetry add <package-name>

   # Development-only dependency
   poetry add --group dev <package-name>
   ```

3. **Regenerate requirements.txt:**
   ```bash
   poetry export -f requirements.txt --output requirements.txt --without-hashes
   ```

4. **Test:**
   ```bash
   python manage.py makemigrations
   python manage.py test --settings=settings.local_test
   ```

5. **Commit** both `pyproject.toml` and `requirements.txt` (and `poetry.lock` once it is tracked).

### Version Pinning Strategy

- Use caret (`^`) version constraints for most dependencies. This allows patch and minor updates while preventing breaking major version changes.
- Use exact pinning (`==`) only for dependencies with a history of breaking changes in minor versions.
- Never use unbounded versions (e.g., `*` or `>=1.0`).

## Deprecated Packages

The following packages are currently in `pyproject.toml` and should be replaced:

| Package | Status | Replacement | Migration Notes |
|---|---|---|---|
| `oauth2client` | **Deprecated since 2017.** No longer maintained. | `google-auth` + `google-auth-httplib2` | `google-auth` is already in the dependency tree (pulled in by `google-api-python-client`). Replace all `oauth2client` imports with `google.auth` and `google.oauth2` equivalents. See [migration guide](https://google-auth.readthedocs.io/en/latest/oauth2client-deprecation.html). |
| `mock` | **Unnecessary.** `unittest.mock` has been in the standard library since Python 3.3. | `unittest.mock` (stdlib) | Replace `from mock import ...` with `from unittest.mock import ...`. Drop `mock` from `pyproject.toml`. |
| `pytz` | **Superseded.** Python 3.9+ includes `zoneinfo` in the standard library. Django 5.x uses `zoneinfo` internally. | `zoneinfo` (stdlib) + `tzdata` (already a dependency) | Replace `pytz.timezone("UTC")` with `zoneinfo.ZoneInfo("UTC")`. Note: `pytz` and `zoneinfo` have different APIs for localization -- `pytz.localize()` is not needed with `zoneinfo`. |
| `drf-yasg` | **Maintenance mode.** Limited Django 5.x support, deprecated by many projects. | `drf-spectacular` | `drf-spectacular` provides OpenAPI 3.0/3.1 support, better Django 5.x compatibility, and is actively maintained. Requires updating Swagger/ReDoc URL configuration and removing `drf-yasg`-specific `SWAGGER_SETTINGS`. |

### Migration Priority

1. **`mock`** -- Low effort, no risk. Can be done immediately.
2. **`pytz`** -- Low-medium effort. Search for all `pytz` usage and replace with `zoneinfo`.
3. **`oauth2client`** -- Medium effort. Requires updating Google Play service account authentication code.
4. **`drf-yasg`** -- Medium-high effort. Requires updating URL configuration, settings, and any custom schema decorators.

## Vulnerability Scanning

### Tools

1. **`pip-audit`** -- Checks installed packages against the Python Packaging Advisory Database.
   ```bash
   pip install pip-audit
   pip-audit
   ```

2. **`safety`** -- Checks dependencies against the Safety vulnerability database.
   ```bash
   pip install safety
   safety check
   ```

3. **GitHub Dependabot** -- Enable Dependabot alerts and security updates in the repository settings. Add `.github/dependabot.yml`:
   ```yaml
   version: 2
   updates:
     - package-ecosystem: "pip"
       directory: "/"
       schedule:
         interval: "weekly"
       open-pull-requests-limit: 10
   ```

### CI Integration

Add vulnerability scanning to the CI pipeline (`.github/workflows/pr_check.yml`):

```yaml
- name: Audit dependencies
  run: |
    pip install pip-audit
    pip-audit --requirement requirements.txt
```

### Response Policy

| Severity | Response Time | Action |
|---|---|---|
| Critical (CVSS 9.0+) | Within 24 hours | Patch or mitigate immediately. Deploy hotfix. |
| High (CVSS 7.0-8.9) | Within 1 week | Update dependency in next release cycle. |
| Medium (CVSS 4.0-6.9) | Within 1 month | Schedule update. Evaluate if exploit is applicable. |
| Low (CVSS 0.1-3.9) | Next scheduled update | Include in regular dependency update cycle. |

### Regular Update Cadence

- **Weekly**: Review Dependabot PRs and security alerts.
- **Monthly**: Run `poetry update` to pick up patch releases. Run `pip-audit` to catch new advisories.
- **Quarterly**: Review all dependencies for major version updates. Evaluate deprecated packages for replacement. Update `pyproject.toml` version constraints as needed.
