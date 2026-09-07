from settings.base import *

# Development only — never enable in production
DEBUG = True
CORS_ALLOW_ALL_ORIGINS = True

INSTALLED_APPS += (
    # other apps for production site
)

ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]", "*"]

# bin/setup writes DATABASE_URL into .env. The fallback below only applies to a
# checkout with no .env, so it points at the standard PostgreSQL port, which is
# also what CI uses.
DATABASES["default"] = dj_database_url.parse(
    os.environ.get("DATABASE_URL", "postgresql://localhost:5432/myapp")
)

SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY

# Get above values from environment variables or use the default values
IDRIVE_ENDPOINT_URL = os.environ.get(
    "IDRIVE_ENDPOINT_URL", "https://k2f7.or.idrivee2-60.com"
)
IDRIVE_ACCESS_KEY = os.environ.get("IDRIVE_ACCESS_KEY", "<access-key>")
IDRIVE_SECRET_ACCESS_KEY = os.environ.get("IDRIVE_SECRET_ACCESS_KEY", "<secret-key>")
IDRIVE_BUCKET_NAME = os.environ.get("IDRIVE_BUCKET_NAME", "central-backend-dev")
CLOUD_STORAGE_BUCKET_NAME = os.environ.get(
    "CLOUD_STORAGE_BUCKET_NAME", "central-backend-dev"
)
CLOUD_STORAGE_PUBLIC_BUCKET_NAME = os.environ.get(
    "CLOUD_STORAGE_PUBLIC_BUCKET_NAME", "central-backend-public-dev"
)
CLOUD_STORAGE_VENDOR = os.environ.get("CLOUD_STORAGE_VENDOR", "idrive")
CLOUD_STORAGE_BUCKET_IS_PUBLIC = os.environ.get(
    "CLOUD_STORAGE_BUCKET_IS_PUBLIC", "false"
)

EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_USE_TLS = ENV.bool("EMAIL_USE_TLS", default=True)
EMAIL_PORT = ENV.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "info@vd.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "pass*")

GOOGLE_PLAY_TYPE = os.environ.get("GOOGLE_PLAY_TYPE", "service_account")
GOOGLE_PLAY_PROJECT_ID = os.environ.get(
    "GOOGLE_PLAY_PROJECT_ID", "probable-maker-123456"
)
GOOGLE_PLAY_PRIVATE_KEY_ID = os.environ.get(
    "GOOGLE_PLAY_PRIVATE_KEY_ID", "privatekeyid"
)
GOOGLE_PLAY_PRIVATE_KEY = os.environ.get(
    "GOOGLE_PLAY_PRIVATE_KEY",
    "-----BEGIN PRIVATE KEY-----\n123456ABCDEFGH\n-----END PRIVATE KEY-----\n",
)
GOOGLE_PLAY_CLIENT_EMAIL = os.environ.get(
    "GOOGLE_PLAY_CLIENT_EMAIL", "google_play_client@email.com"
)
GOOGLE_PLAY_CLIENT_ID = os.environ.get("GOOGLE_PLAY_CLIENT_ID", "123456")
GOOGLE_PLAY_AUTH_URI = os.environ.get(
    "GOOGLE_PLAY_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"
)
GOOGLE_PLAY_TOKEN_URI = os.environ.get(
    "GOOGLE_PLAY_TOKEN_URI", "https://oauth2.googleapis.com/token"
)
GOOGLE_PLAY_AUTH_PROVIDER_X509_CERT_URL = os.environ.get(
    "GOOGLE_PLAY_AUTH_PROVIDER_X509_CERT_URL",
    "https://www.googleapis.com/oauth2/v1/certs",
)
GOOGLE_PLAY_CLIENT_X509_CERT_URL = os.environ.get(
    "GOOGLE_PLAY_CLIENT_X509_CERT_URL",
    "https://www.googleapis.com/robot/v1/metadata/x509/backend-developer-api%40probable-maker-123456.iam.gserviceaccount.com",
)
GOOGLE_PLAY_UNIVERSE_DOMAIN = os.environ.get(
    "GOOGLE_PLAY_UNIVERSE_DOMAIN", "googleapis.com"
)

NETGSM_USER_CODE = os.environ.get("NETGSM_USER_CODE", "8500000000")
NETGSM_PASSWORD = os.environ.get("NETGSM_PASSWORD", "123456")
SMS_HEADER = os.environ.get("SMS_HEADER", "VD")

SWAGGER_ACCESS_PASSCODE = os.environ.get("SWAGGER_ACCESS_PASSCODE", "swagger")

SOCIAL_SECRET = os.environ.get("SOCIAL_SECRET", "dev-social-secret-123")

try:
    from settings.local_overrides import *
except Exception:
    pass
