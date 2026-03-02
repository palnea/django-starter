# Secrets Management

## 12-Factor Principles

This project follows the [12-Factor App](https://12factor.net/config) methodology for configuration management. The core principle is:

> Store config in the environment, not in code.

All secrets and environment-specific configuration are injected via environment variables, never hard-coded in source files. The `django-environ` library (`environ.Env`) reads these values at startup from either the process environment or a local `.env` file.

### How It Works in This Project

1. `settings/base.py` initializes `ENV = environ.Env(...)` and reads from a `.env` file if present.
2. Each setting that contains a secret uses `os.environ.get("VAR_NAME")` or `ENV("VAR_NAME")`.
3. Environment-specific settings modules (`settings/development.py`, `settings/prod.py`, etc.) override only what differs per environment.
4. The `.env` file is listed in `.gitignore` and must never be committed.

## .env File Management

### Local Development

Create a `.env` file in the project root with the required variables. A `.env.example` template should be maintained (but never contain real secrets):

```bash
cp .env.example .env
# Edit .env with your local values
```

### Rules

- `.env` is in `.gitignore` -- it must never be committed.
- Never share `.env` files through chat, email, or ticketing systems.
- Each developer maintains their own local `.env`.
- Use `local_overrides.py` (also git-ignored) for Python-level local overrides if needed.

## Required Environment Variables

### Core Django

| Variable | Required | Description | Example |
|---|---|---|---|
| `SECRET_KEY` | Yes (prod) | Django secret key and JWT signing key | Random 50+ char string |
| `DATABASE_URL` | Yes | PostgreSQL connection string | `postgres://user:pass@host:5432/dbname` |
| `SWAGGER_ACCESS_PASSCODE` | Yes | Passcode to access Swagger UI | Any string |

### Cloud Storage (IDrive / AWS S3)

| Variable | Required | Description |
|---|---|---|
| `IDRIVE_ENDPOINT_URL` | If using IDrive | IDrive S3-compatible endpoint |
| `IDRIVE_ACCESS_KEY` | If using IDrive | IDrive access key |
| `IDRIVE_SECRET_ACCESS_KEY` | If using IDrive | IDrive secret key |
| `IDRIVE_BUCKET_NAME` | If using IDrive | IDrive bucket name |
| `CLOUD_STORAGE_BUCKET_NAME` | Yes | Primary storage bucket |
| `CLOUD_STORAGE_PUBLIC_BUCKET_NAME` | Yes | Public-accessible bucket |
| `CLOUD_STORAGE_VENDOR` | Yes | Storage vendor identifier |
| `CLOUD_STORAGE_BUCKET_IS_PUBLIC` | Yes | Whether bucket is public |
| `AWS_S3_ACCESS_KEY_ID` | If using AWS | AWS access key |
| `AWS_S3_SECRET_ACCESS_KEY` | If using AWS | AWS secret key |

### Google Play Store

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_PLAY_RSA_KEY` | If using GP | RSA key for receipt validation |
| `GOOGLE_PLAY_PACKAGE_NAME` | If using GP | Android package name |
| `GOOGLE_PLAY_TYPE` | If using GP | Service account type |
| `GOOGLE_PLAY_PROJECT_ID` | If using GP | GCP project ID |
| `GOOGLE_PLAY_PRIVATE_KEY_ID` | If using GP | Service account private key ID |
| `GOOGLE_PLAY_PRIVATE_KEY` | If using GP | Service account private key (PEM) |
| `GOOGLE_PLAY_CLIENT_EMAIL` | If using GP | Service account email |
| `GOOGLE_PLAY_CLIENT_ID` | If using GP | Service account client ID |
| `GOOGLE_PLAY_AUTH_URI` | If using GP | OAuth2 auth URI |
| `GOOGLE_PLAY_TOKEN_URI` | If using GP | OAuth2 token URI |
| `GOOGLE_PLAY_AUTH_PROVIDER_X509_CERT_URL` | If using GP | Auth provider cert URL |
| `GOOGLE_PLAY_CLIENT_X509_CERT_URL` | If using GP | Client cert URL |
| `GOOGLE_PLAY_UNIVERSE_DOMAIN` | If using GP | Universe domain |

### Apple Services

| Variable | Required | Description |
|---|---|---|
| `SOCIAL_AUTH_APPLE_KEY_ID` | If using Apple auth | Apple Sign-In key ID |
| `SOCIAL_AUTH_APPLE_TEAM_ID` | If using Apple auth | Apple developer team ID |
| `SOCIAL_AUTH_APPLE_PRIVATE_KEY` | If using Apple auth | Apple Sign-In private key (PEM) |
| `APPLE_IN_APP_SIGNING_KEY` | If using IAP | In-app purchase signing key |
| `APPLE_BUNDLE_ID` | If using Apple | App bundle identifier |
| `APPLE_DEVELOPER_KEY_ID` | If using Apple | Developer key ID |
| `APPLE_DEVELOPER_ISSUER_ID` | If using Apple | Developer issuer ID |
| `APPLE_APP_ID` | If using Apple | App Store app ID |
| `APPLE_CONNECT_API_KEY_ID` | If using Apple | App Store Connect API key ID |
| `APPLE_CONNECT_API_SIGNING_KEY` | If using Apple | App Store Connect signing key |

### Social Authentication

| Variable | Required | Description |
|---|---|---|
| `SOCIAL_SECRET` | Yes | Shared secret for social auth token exchange |

### SMS / Email

| Variable | Required | Description |
|---|---|---|
| `SMS_HEADER` | If using SMS | SMS sender header |
| `NETGSM_USER_CODE` | If using SMS | NetGSM account code |
| `NETGSM_PASSWORD` | If using SMS | NetGSM account password |
| `EMAIL_HOST` | If using email | SMTP server hostname |
| `EMAIL_USE_TLS` | If using email | Enable TLS (`True`/`False`) |
| `EMAIL_PORT` | If using email | SMTP port |
| `EMAIL_HOST_USER` | If using email | SMTP username |
| `EMAIL_HOST_PASSWORD` | If using email | SMTP password |

### Celery / Redis

| Variable | Required | Description | Default |
|---|---|---|---|
| `CELERY_BROKER_URL` | No | Redis connection for Celery broker | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | No | Celery result backend | `django-db` |

## Secret Rotation

### Rotation Procedure

1. **Generate a new secret** using a cryptographically secure method:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

2. **Update the secret** in your production secrets manager (e.g., Heroku config vars, AWS Secrets Manager, or platform environment settings).

3. **Restart application processes** to pick up the new value. Django reads environment variables at process startup, so a restart is required.

4. **Verify** by checking application health endpoints and monitoring for authentication errors.

### Key-Specific Notes

| Secret | Rotation Impact | Notes |
|---|---|---|
| `SECRET_KEY` | Invalidates all existing JWT tokens and Django sessions | Users will need to re-authenticate |
| `DATABASE_URL` | Requires coordinated DB credential rotation | Update DB user password first, then env var |
| `IDRIVE_*` / `AWS_S3_*` | May briefly interrupt file uploads/downloads | Rotate during low-traffic periods |
| `SOCIAL_AUTH_APPLE_PRIVATE_KEY` | Invalidates Apple Sign-In flow | Coordinate with Apple Developer portal |
| `NETGSM_PASSWORD` | Interrupts SMS sending | Rotate via NetGSM dashboard |
| `EMAIL_HOST_PASSWORD` | Interrupts email sending | Rotate via email provider |

### Rotation Schedule

- `SECRET_KEY`: Rotate every 6 months or after any team member departure.
- Database credentials: Rotate every 3-6 months.
- Third-party API keys (Apple, Google, IDrive): Rotate annually or upon suspected compromise.
- SMS/Email credentials: Rotate annually.

## Production Secrets

### Principles

1. **Never commit secrets to version control.** The `.env` file and `local_overrides.py` are both git-ignored.
2. **Use your platform's secrets management.** Examples:
   - Heroku: `heroku config:set SECRET_KEY=...`
   - AWS: Secrets Manager or Parameter Store
   - GCP: Secret Manager
   - Kubernetes: Secrets objects mounted as env vars
3. **Restrict access.** Only DevOps and designated engineers should have access to production secrets.
4. **Audit access.** Use platform audit logs to track who accessed or modified secrets.
5. **Separate environments.** Development, staging, and production must each have their own set of secrets. Never reuse production secrets in lower environments.

### Current Concerns

- `settings/base.py` contains a hard-coded fallback `SECRET_KEY` (`django-insecure-...`). This is acceptable for local development only. In production, `settings/prod.py` overrides it with `os.environ.get("SECRET_KEY")`.
- `SOCIAL_SECRET` has a default value of `"default-social-secret-key"` in `base.py`. This default must be overridden in production via environment variable.
- The `SIMPLE_JWT["SIGNING_KEY"]` is set to `os.environ.get("SECRET_KEY")` in both `base.py` (line 273) and `prod.py`. Ensure `SECRET_KEY` is always set in production.

### Checklist Before Deploying to Production

- [ ] `SECRET_KEY` is set to a unique, random value (not the insecure default).
- [ ] `DATABASE_URL` points to the production database with restricted credentials.
- [ ] `SOCIAL_SECRET` is set to a strong, unique value.
- [ ] `DEBUG` is `False` (enforced in `prod.py`).
- [ ] `ALLOWED_HOSTS` is set to production domain(s) only.
- [ ] `CORS_ALLOWED_ORIGINS` lists only trusted origins.
- [ ] All third-party API keys (Apple, Google, IDrive/AWS) are production keys.
- [ ] `.env` file does not exist on the production server (use platform env vars instead).
