# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Django Project Structure

This is a Django REST Framework project with the following key structure:

- **manage/**: Django project root containing settings.py, urls.py, wsgi.py, asgi.py
- **settings/**: Environment-specific Django settings
  - `base.py`: Base settings imported by all environments
  - `development.py`: Development-specific settings  
  - `test.py`: Test environment settings
  - `prod.py`: Production settings
  - `local_test.py`: Local test settings (removes logger app)
- **Custom Apps**: authy, user, common, contact_verification, payment, subscription, vendor, logger
- **utils/**: Shared utilities and helpers
- **custom_test/**: Custom test base classes and utilities
- **staticfiles/**: Static files for production
- **locale/**: Internationalization files (en, tr)

## Key Configuration

- **Authentication**: Custom JWT authentication via `authy.utils.custom_jwt_authentication.CustomJWTAuthentication`
- **Custom User Model**: `user.User` (AUTH_USER_MODEL) - Unified model combining authentication and user profile
- **Database**: PostgreSQL with dj-database-url
- **API Documentation**: Swagger UI at `/swagger/` and ReDoc at `/redoc/`
- **Internationalization**: Supports English and Turkish
- **Cloud Storage**: IDrive/AWS S3 integration
- **Payment**: Apple App Store and Google Play Store integration
- **Monitoring**: New Relic integration via gunicorn.conf.py

## Development Commands

### Testing
```bash
# Run all tests (generates migrations first)
python manage.py test --settings=settings.local_test

# Run tests for specific app
python manage.py test authy.test --settings=settings.local_test

# Run specific test file
python manage.py test custom_test.test_check_permissions --settings=settings.local_test
```

### Migrations
```bash
# Generate migrations (always run before tests)
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Note: Migration files are excluded from git commits
```

### Code Quality
```bash
# Format code with Black
black .

# Check formatting
black --check .
```

### Internationalization
```bash
# Compile translation messages
python manage.py compilemessages

# Extract translatable strings
python manage.py makemessages -l tr
```

### Development Server
```bash
# Run development server
python manage.py runserver

# Run with specific settings
python manage.py runserver --settings=settings.development
```

### Static Files
```bash
# Collect static files (for production)
python manage.py collectstatic --noinput
```

## Testing Guidelines

- **Base Test Class**: Use `CustomIntegrationTestCase` or `CustomAPITestCase` from `custom_test/base_test.py`
- **Test Location**: Tests are in `{app}/test/test_integration.py` files
- **Test Settings**: Always use `--settings=settings.local_test` 
- **Migration Requirement**: Generate migrations before running tests
- **Test Database**: Uses PostgreSQL in CI, configured via DATABASE_URL

## CI/CD

The project uses GitHub Actions for PR checks (`.github/workflows/pr_check.yml`):
- Black code formatting check
- Django test suite with PostgreSQL
- Migration generation and compilation
- Tests run against all test directories

## Important Notes

- **Migration Files**: Always excluded from git commits - generate locally before testing
- **Settings Import**: `manage/settings.py` imports from `settings/*` 
- **Environment Variables**: Managed via django-environ and .env files
- **Custom Middleware**: Global context, health check, swagger access control
- **Permission System**: Uses Django groups and permissions
- **Soft Delete**: Implemented via django-soft-delete
- **Phone Numbers**: Handled via django-phonenumber-field
- **API Pagination**: Custom pagination class in `common.pagination`
- **Social Authentication**: Uses `SOCIAL_SECRET` setting for social login password generation

## Architecture Notes

- **Service Layer**: Business logic in `{app}/services.py` files
- **Custom Exceptions**: Centralized in `common/custom_exceptions/`
- **Response Handling**: Standardized via `common/response/view_response.py`
- **Logging**: Structured logging with custom processors
- **Authentication Flow**: JWT tokens with refresh rotation using unified User model
- **File Upload**: Cloud storage abstraction in `cloud_storage/`
- **Social Auth**: Apple, Google, Facebook integration in `authy/social_auth/`
- **User Management**: Unified User model with authentication, profile, and permissions
- **Django Admin**: Accessible with email/username + password (no separate Account model)