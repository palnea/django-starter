# BetterStack Integration Setup Guide

This Django application has been migrated from New Relic to BetterStack for comprehensive monitoring, logging, and APM capabilities.

## Why BetterStack?

BetterStack provides excellent value with its free tier and cost-effective pricing:

- **Free Tier Benefits:**
  - 3GB logs with 3-day retention
  - 2B metrics with 30-day retention
  - APM features and distributed tracing
  - Real-time log search and analysis
  - Custom dashboards and alerting

- **Cost Effective:** ~90% cheaper than Datadog
- **Better APM:** More comprehensive than Sentry
- **Simpler Pricing:** Transparent, predictable costs
- **Excellent Django Integration:** Out-of-the-box support

## Setup Instructions

### 1. Create BetterStack Account

1. Sign up for a free account at [betterstack.com](https://betterstack.com)
2. Navigate to your dashboard
3. Create a new source for your Django application
4. Copy the source token

### 2. Environment Configuration

Add the following environment variable to your `.env` file:

```bash
# BetterStack Configuration
BETTERSTACK_SOURCE_TOKEN=your_source_token_here
```

### 3. Install Dependencies

The required dependencies are already included in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key packages added:
- `logtail-python==0.2.13` - BetterStack Python client
- `python-json-logger==2.0.7` - JSON logging formatter

### 4. Configuration Details

The migration includes:

#### Django Logging Configuration
- Comprehensive logging setup in `settings/base.py`
- Multiple log levels (INFO, ERROR, WARNING)
- Application-specific loggers for different modules
- JSON formatting for structured logs

#### APM Middleware
- Custom middleware (`BetterStackAPMMiddleware`) for request tracking
- Monitors request duration, response codes, and errors
- Tracks slow requests (>2 seconds) as warnings
- Captures user context and IP addresses

#### Structured Logging
- Structlog integration for enhanced logging capabilities
- Automatic log forwarding to BetterStack
- Fallback to console logging in development

## Features Available

### 📊 Application Performance Monitoring (APM)
- **Request Tracking:** Monitor all HTTP requests with timing
- **Response Time Metrics:** Track average, p95, p99 response times
- **Throughput Monitoring:** Requests per second/minute
- **Error Rate Tracking:** 4xx/5xx error percentages
- **Endpoint Performance:** Per-endpoint performance breakdown

### 📝 Comprehensive Logging
- **Structured Logs:** JSON-formatted logs with rich context
- **Real-time Search:** Query logs instantly with powerful filters
- **Log Correlation:** Connect logs to specific requests/users
- **Multiple Log Levels:** INFO, WARNING, ERROR with appropriate routing
- **Application Logs:** Dedicated loggers for each Django app

### 🚨 Alerting & Monitoring
- **Error Alerts:** Get notified of application errors
- **Performance Alerts:** Alerts for slow requests or high error rates
- **Custom Dashboards:** Build dashboards for your specific metrics
- **SLA Monitoring:** Track uptime and performance SLAs

### 🔍 Error Tracking
- **Exception Capture:** Automatic exception logging with full context
- **Stack Traces:** Complete error details for debugging
- **User Impact:** See which users are affected by errors
- **Error Grouping:** Similar errors grouped for easier management

## Usage Examples

### Custom Logging in Your Views

```python
import structlog

logger = structlog.get_logger(__name__)

def my_view(request):
    logger.info(
        "user_action",
        action="profile_update",
        user_id=request.user.id,
        timestamp=timezone.now().isoformat()
    )
    
    try:
        # Your business logic
        pass
    except Exception as e:
        logger.error(
            "operation_failed",
            error=str(e),
            user_id=request.user.id,
            operation="profile_update"
        )
        raise
```

### Performance Monitoring

The APM middleware automatically tracks:
- Request duration for all endpoints
- HTTP status codes
- User context (if authenticated)
- Slow request warnings
- Error details with stack traces

### Custom Metrics

```python
import structlog

logger = structlog.get_logger(__name__)

# Track business metrics
logger.info(
    "business_metric",
    metric_name="user_signup",
    value=1,
    user_type="premium",
    source="web"
)

# Track database query performance
logger.info(
    "database_query",
    query_type="user_lookup",
    duration_ms=45,
    table="users"
)
```

## Dashboard Setup

### 1. Request Performance Dashboard
Create dashboards tracking:
- Average response time by endpoint
- Request volume over time
- Error rate trends
- Slowest endpoints

### 2. Application Health Dashboard
Monitor:
- Error count and types
- User activity patterns
- System resource usage
- Critical business metrics

### 3. Alerting Rules
Set up alerts for:
- Error rate > 5%
- Average response time > 2 seconds
- Critical errors (500 status codes)
- Specific business metric thresholds

## Querying Logs

BetterStack provides powerful log querying capabilities:

```sql
-- Find all errors in the last hour
level:ERROR @timestamp:[now-1h TO now]

-- Track slow requests
event:slow_request duration_ms:>2000

-- Monitor specific user activity
user_id:12345 event:request_completed

-- API endpoint performance
endpoint:/api/users/ status_code:200
```

## Migration Notes

### Removed New Relic Components
- ❌ `newrelic` package dependency
- ❌ New Relic agent initialization in `gunicorn.conf.py`
- ❌ New Relic logging processor
- ❌ New Relic configuration files (`settings/logger/*.ini`)

### Added BetterStack Components
- ✅ `logtail-python` package
- ✅ BetterStack logging processor with structured logging
- ✅ APM middleware for request tracking
- ✅ Comprehensive Django logging configuration
- ✅ Environment-based configuration

## Troubleshooting

### Common Issues

1. **Logs not appearing in BetterStack**
   - Verify `BETTERSTACK_SOURCE_TOKEN` is set correctly
   - Check console output for error messages
   - Ensure internet connectivity for log forwarding

2. **APM metrics missing**
   - Confirm middleware is properly added to `MIDDLEWARE` list
   - Check that middleware is not being bypassed by other middleware

3. **Performance impact**
   - The middleware adds minimal overhead (~1-2ms per request)
   - Logging is asynchronous and non-blocking
   - Monitor your application performance after deployment

### Debug Mode
In development, logs are printed to console and also sent to BetterStack (if token is configured).

### Health Check
Verify the setup with:

```python
import structlog
logger = structlog.get_logger(__name__)
logger.info("betterstack_test", message="Integration working correctly")
```

## Cost Optimization

### Free Tier Optimization
- The free tier provides 3GB logs (3-day retention)
- Monitor your log volume in BetterStack dashboard
- Use log levels appropriately (avoid excessive DEBUG logging in production)

### Scaling Considerations
- BetterStack pricing scales predictably with data volume
- Consider log retention policies for cost management
- Use structured logging for better query performance

## Support

For issues with:
- **BetterStack Platform:** Contact BetterStack support
- **Integration Code:** Review this documentation or create an issue
- **Django Configuration:** Check Django logging documentation

## Next Steps

1. Set up your BetterStack account and get the source token
2. Configure the environment variable
3. Deploy the application
4. Create dashboards and alerts in BetterStack
5. Test the monitoring with some sample requests
6. Set up alerting rules for your team

Enjoy comprehensive monitoring with BetterStack! 🚀 