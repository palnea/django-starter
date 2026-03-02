# On-Call / Incident Response

## Monitoring Stack

- **APM:** New Relic (configured via `gunicorn.conf.py` and environment-specific `.ini` files in `settings/logger/`)
- **Logging:** structlog with New Relic log forwarding via `logger/logging_processors.py`
- **Health check:** `HealthCheckMiddleware` at `/health/` (bypasses all other middleware)

## Alerting Rules

### Critical Alerts (Page Immediately)

| Alert Name                  | Condition                                                    | Duration | Channel       |
|-----------------------------|--------------------------------------------------------------|----------|---------------|
| High error rate             | HTTP 5xx rate > 5% of total requests                         | 3 min    | PagerDuty/SMS |
| Application not responding  | Health check (`/health/`) fails                              | 2 min    | PagerDuty/SMS |
| DB connection exhaustion    | PostgreSQL active connections > 90% of `max_connections`     | 2 min    | PagerDuty/SMS |
| Worker process crash        | Gunicorn worker restart count > 5 in 10 minutes              | 10 min   | PagerDuty/SMS |
| Celery queue backlog        | Redis queue length > 1000 tasks                              | 5 min    | PagerDuty/SMS |
| JWT signing key missing     | `SECRET_KEY` env var is unset (app fails to start)           | 0 min    | PagerDuty/SMS |

### Warning Alerts (Investigate During Business Hours)

| Alert Name                  | Condition                                                    | Duration | Channel    |
|-----------------------------|--------------------------------------------------------------|----------|------------|
| Elevated error rate         | HTTP 5xx rate > 1% of total requests                         | 10 min   | Slack      |
| Slow response times         | p95 response time > 2 seconds                                | 10 min   | Slack      |
| Throttle spike              | `ERR_THROTTLED` count > 100 in 5 minutes                     | 5 min    | Slack      |
| Disk usage high             | Disk usage > 80%                                             | 15 min   | Slack      |
| Celery task failures        | Task failure rate > 10% in 15 minutes                        | 15 min   | Slack      |
| Certificate expiry          | TLS certificate expires within 14 days                       | Daily    | Slack      |

## Escalation Path

```
Level 1 (0-15 min)   : On-call engineer (auto-paged)
Level 2 (15-30 min)  : Secondary on-call / team lead
Level 3 (30-60 min)  : Engineering manager
Level 4 (60+ min)    : CTO / VP Engineering
```

### Responsibilities by Level

| Level | Who                  | Can Do                                                    |
|-------|----------------------|-----------------------------------------------------------|
| L1    | On-call engineer     | Restart services, scale workers, toggle feature flags, apply known runbooks |
| L2    | Team lead            | Approve emergency deploys, coordinate cross-team response |
| L3    | Engineering manager  | Approve data fixes, customer communication decisions      |
| L4    | CTO / VP Engineering | Approve infrastructure changes, external vendor escalation|

## Runbooks

### Runbook: High Error Rate (5xx Spike)

**Symptoms:** New Relic alert for 5xx rate > 5%. Users reporting failures.

**Steps:**

1. **Identify the failing endpoint(s):**
   - New Relic > APM > Errors > Group by transaction name.
   - Look for `ERR_INTERNAL_SERVER_ERROR` or `ERR_UNKNOWN_ERROR` in structured logs.

2. **Check recent deployments:**
   ```bash
   git log --oneline -10
   ```
   If a deploy happened in the last 30 minutes, consider rollback:
   ```bash
   # Roll back to previous release (platform-specific)
   ```

3. **Check database connectivity:**
   ```bash
   python manage.py dbshell -c "SELECT 1;"
   ```

4. **Check external service dependencies:**
   - Apple App Store API (payment verification)
   - Google Play API (payment verification)
   - IDrive / S3 (file storage)
   - SMTP (email sending)
   - NetGSM (SMS sending)

5. **Check application logs:**
   - Filter structlog output for `log_level=error` in the last 15 minutes.
   - Look for exception stack traces containing `CustomException` vs unexpected exceptions.

6. **Restart workers if necessary:**
   ```bash
   # Graceful restart (no dropped requests)
   kill -HUP <gunicorn_master_pid>
   ```

7. **If caused by a specific endpoint, disable via feature flag (if available) or apply a temporary code fix.**

8. **Notify stakeholders once mitigated.**

---

### Runbook: Database Connection Exhaustion

**Symptoms:** New Relic alert for high DB connection count. Application returning 500 errors with `OperationalError: connection pool exhausted` or similar.

**Steps:**

1. **Confirm the issue:**
   ```sql
   -- Connect to PostgreSQL directly
   SELECT count(*) FROM pg_stat_activity WHERE datname = '<db_name>';
   SELECT max_conn FROM (SELECT setting::int AS max_conn FROM pg_settings WHERE name = 'max_connections') t;
   ```

2. **Identify connection consumers:**
   ```sql
   SELECT client_addr, usename, state, count(*)
   FROM pg_stat_activity
   WHERE datname = '<db_name>'
   GROUP BY client_addr, usename, state
   ORDER BY count DESC;
   ```

3. **Check for long-running queries:**
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
   FROM pg_stat_activity
   WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
     AND state != 'idle'
   ORDER BY duration DESC;
   ```

4. **Kill long-running queries (if safe):**
   ```sql
   SELECT pg_terminate_backend(<pid>);
   ```

5. **Check for connection leaks in application code:**
   - Look for raw database connections (`connection.cursor()`) that are not properly closed.
   - Check Celery tasks that may hold connections open.

6. **Temporary mitigation -- restart Gunicorn to release all connections:**
   ```bash
   kill -HUP <gunicorn_master_pid>
   ```

7. **If recurring, increase connection pool size or add PgBouncer as a connection pooler.**

8. **Verify Celery workers are not accumulating idle connections:**
   ```bash
   celery -A manage inspect active
   ```

---

### Runbook: Celery Queue Backlog

**Symptoms:** Redis queue length growing. Async tasks (email, SMS, payment verification) delayed.

**Steps:**

1. **Check queue length:**
   ```bash
   redis-cli -u $CELERY_BROKER_URL LLEN celery
   ```

2. **Check worker status:**
   ```bash
   celery -A manage inspect active
   celery -A manage inspect reserved
   ```

3. **Check for stuck tasks:**
   ```bash
   celery -A manage inspect active --timeout=10
   ```

4. **Scale workers if needed.**

5. **If a specific task type is failing repeatedly, disable it via Celery Beat admin or revoke pending tasks:**
   ```bash
   celery -A manage purge  # WARNING: discards all pending tasks
   ```

## Postmortem Template

After every Critical alert that results in user-facing impact, write a postmortem within 48 hours. Use the following template:

---

```markdown
# Postmortem: [Incident Title]

**Date:** YYYY-MM-DD
**Duration:** HH:MM - HH:MM UTC (X minutes)
**Severity:** Critical / Warning
**Author:** [Name]
**Status:** Draft / Reviewed / Complete

## Summary

[1-2 sentence description of what happened and the user impact.]

## Timeline (UTC)

| Time  | Event                                           |
|-------|--------------------------------------------------|
| HH:MM | Alert triggered: [alert name]                   |
| HH:MM | On-call engineer acknowledged                   |
| HH:MM | Root cause identified                           |
| HH:MM | Mitigation applied                              |
| HH:MM | Service fully restored                          |
| HH:MM | Alert resolved                                  |

## Root Cause

[Detailed technical explanation of what caused the incident.]

## Impact

- **Users affected:** [number or percentage]
- **Requests failed:** [count or percentage]
- **Duration of impact:** [minutes]
- **Revenue impact:** [if applicable]

## Detection

- How was the incident detected? (alert / customer report / manual observation)
- How long between start of impact and detection?

## Mitigation

[What was done to stop the bleeding? Rollback, restart, config change, etc.]

## Resolution

[What was done to fully resolve the issue? Code fix, infrastructure change, etc.]

## Action Items

| Action                                        | Owner       | Priority | Due Date   |
|-----------------------------------------------|-------------|----------|------------|
| [Specific corrective action]                  | [Name]      | P0/P1/P2 | YYYY-MM-DD |
| [Preventive measure]                          | [Name]      | P0/P1/P2 | YYYY-MM-DD |
| [Monitoring improvement]                      | [Name]      | P0/P1/P2 | YYYY-MM-DD |

## Lessons Learned

### What went well

- [e.g., Alert fired within 2 minutes of impact start]

### What could be improved

- [e.g., Runbook was outdated and did not cover this scenario]

### Where we got lucky

- [e.g., Incident happened during low-traffic hours]
```

---

## On-Call Expectations

- **Rotation:** Weekly, starting Monday 09:00 UTC.
- **Acknowledgement SLA:** Critical alerts must be acknowledged within 15 minutes.
- **Laptop and connectivity:** On-call engineer must have laptop access and reliable internet throughout the rotation.
- **Handoff:** Outgoing on-call writes a brief handoff note covering any ongoing issues or recent changes.
- **Compensation:** Follow company on-call compensation policy.
