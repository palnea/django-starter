# Security Hardening Checklist

An OWASP-inspired checklist tailored to this Django REST Framework project.
Review each item before any production deployment.

---

## 1. Authentication & Session Management

- [ ] `SECRET_KEY` is loaded from environment variable in production (never the insecure default from `base.py`)
- [ ] `SIMPLE_JWT["SIGNING_KEY"]` uses a dedicated secret, not the Django `SECRET_KEY`
- [ ] Access token lifetime (`ACCESS_TOKEN_LIFETIME`) is 15 minutes or less
- [ ] Refresh token lifetime (`REFRESH_TOKEN_LIFETIME`) is appropriate for the threat model (currently 30 days)
- [ ] `ROTATE_REFRESH_TOKENS` is `True` so each refresh issues a new token
- [ ] `BLACKLIST_AFTER_ROTATION` is `True` in production to prevent refresh-token replay
- [ ] `SOCIAL_SECRET` is set to a strong random value (not the default `"default-social-secret-key"`)
- [ ] Password validators are all enabled (`UserAttributeSimilarityValidator`, `MinimumLengthValidator`, `CommonPasswordValidator`, `NumericPasswordValidator`)
- [ ] Account lockout or rate limiting is applied to login endpoints (e.g., `django-axes`, `django-ratelimit`, or DRF throttling)
- [ ] Session cookies use `SESSION_COOKIE_SECURE = True` and `SESSION_COOKIE_HTTPONLY = True`
- [ ] `CSRF_COOKIE_SECURE = True` in production
- [ ] Social auth tokens (Apple, Google, Facebook) are validated server-side before trust

## 2. Authorization

- [ ] `DEFAULT_PERMISSION_CLASSES` is set to `IsAuthenticated` (confirmed in `base.py`)
- [ ] Every viewset explicitly declares `permission_classes` (prefer `ShortCircuitOr(ActionAwareModelPermissions, IsOwner)`)
- [ ] `OwnershipMixin` is used on all user-scoped viewsets to enforce row-level access
- [ ] Admin endpoints (`/admin/`) are restricted by IP or VPN in production
- [ ] Swagger/ReDoc endpoints are gated by `SWAGGER_ACCESS_PASSCODE` and disabled or password-protected in production
- [ ] Django model permissions are assigned via groups, not directly to users
- [ ] Custom actions use `{app_label}.{view_name}_{action}` permission naming convention
- [ ] No endpoint returns data belonging to other users without explicit admin permission

## 3. Transport Security

- [ ] `SECURE_SSL_REDIRECT = True` in production settings
- [ ] `SECURE_HSTS_SECONDS` is set (e.g., `31536000` for one year)
- [ ] `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- [ ] `SECURE_HSTS_PRELOAD = True`
- [ ] `SECURE_PROXY_SSL_HEADER` is configured if behind a reverse proxy (e.g., `("HTTP_X_FORWARDED_PROTO", "https")`)
- [ ] TLS 1.2+ is enforced at the load balancer / reverse proxy level
- [ ] All external API calls (Apple, Google Play, IDrive/S3) use HTTPS

## 4. CORS

- [ ] `CORS_ALLOW_ALL_ORIGINS = False` in all environments (confirmed in `base.py` and `prod.py`)
- [ ] `CORS_ALLOWED_ORIGINS` is an explicit allowlist of trusted domains
- [ ] `CORS_ALLOW_CREDENTIALS` is `False` unless cookies must be sent cross-origin
- [ ] `CORS_ALLOW_HEADERS` and `CORS_ALLOW_METHODS` are scoped to only what the front-end needs
- [ ] No wildcard (`*`) origins are permitted in staging or production

## 5. Input Validation

- [ ] All user input passes through DRF serializers before reaching services
- [ ] `get_serializer_class()` returns action-specific serializers to limit writable fields per operation
- [ ] File uploads are validated for type, size, and content (not just extension)
- [ ] Phone numbers are validated via `django-phonenumber-field`
- [ ] Query parameters used in `filter_backends` are restricted to declared `filterset_fields`
- [ ] No raw SQL queries exist; all database access goes through the ORM
- [ ] JSON request bodies are bounded in size at the web server / load balancer level
- [ ] `APPEND_SLASH = True` prevents path-traversal edge cases in routing

## 6. Secrets Management

- [ ] All secrets are loaded from environment variables or a secrets manager (never hard-coded)
- [ ] `.env` files are listed in `.gitignore` and never committed
- [ ] Google Play service-account credentials (`GOOGLE_PLAY_PRIVATE_KEY`, etc.) are injected at runtime
- [ ] Apple signing keys (`SOCIAL_AUTH_APPLE_PRIVATE_KEY`, `APPLE_IN_APP_SIGNING_KEY`) are injected at runtime
- [ ] IDrive / AWS S3 credentials (`IDRIVE_SECRET_ACCESS_KEY`, `AWS_S3_SECRET_ACCESS_KEY`) are injected at runtime
- [ ] SMTP credentials (`EMAIL_HOST_PASSWORD`) are injected at runtime
- [ ] NetGSM credentials (`NETGSM_PASSWORD`) are injected at runtime
- [ ] Celery broker URL (`CELERY_BROKER_URL`) uses authentication and TLS in production
- [ ] Secrets are rotated on a regular schedule
- [ ] CI/CD secrets are stored in GitHub Actions encrypted secrets, not in workflow files

## 7. Dependencies

- [ ] `poetry.lock` is committed and used for deterministic installs (`poetry install --no-root`)
- [ ] Dependency audit is run regularly (`pip-audit`, `safety check`, or GitHub Dependabot)
- [ ] No unnecessary packages are included in production dependencies
- [ ] `psycopg2-binary` is replaced with `psycopg2` (compiled) in production for stability
- [ ] Python version (`^3.14`) is kept up to date with security patches
- [ ] Django and DRF are updated promptly when security releases are published
- [ ] Third-party packages with known CVEs are patched or replaced

## 8. Observability & Incident Response

- [ ] Structured logging via `structlog` is active and ships to a centralized platform (New Relic)
- [ ] `log_view_response()` is called in every view method so all requests are auditable
- [ ] Failed authentication attempts are logged with source IP
- [ ] 4xx and 5xx responses are distinguishable in logs (`warning` vs `error` log levels)
- [ ] Error responses follow RFC 7807 format and never leak stack traces to clients
- [ ] `DEBUG = False` in production (confirmed in `prod.py`)
- [ ] `ALLOWED_HOSTS` is set to the exact production domain(s) (currently empty in `prod.py` -- must be populated)
- [ ] Health-check endpoint (`HealthCheckMiddleware`) does not expose sensitive information
- [ ] Alerting is configured for anomalous error rates, latency spikes, and auth failures
- [ ] An incident-response runbook exists and is tested periodically

## 9. Additional Django-Specific Hardening

- [ ] `X-Frame-Options` middleware is active (`XFrameOptionsMiddleware` -- confirmed)
- [ ] `X-Content-Type-Options: nosniff` is set via `SECURE_CONTENT_TYPE_NOSNIFF = True`
- [ ] `SecurityMiddleware` is in the middleware stack (confirmed)
- [ ] Admin panel uses a non-default URL path (not `/admin/`)
- [ ] `django.contrib.sessions` session engine uses database or cache backend, not signed cookies for sensitive data
- [ ] Migration files are never committed to source control (per project policy)
- [ ] `DEFAULT_AUTO_FIELD` is set to `BigAutoField` (confirmed) to prevent integer overflow on high-volume tables
