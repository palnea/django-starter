from enum import Enum, auto
from types import DynamicClassAttribute


class GeneralErrorCode(Enum):
    """
    Standardized codes for general (non-field) errors.
    These codes are used in the 'general' errors section of structured error responses.
    """

    # Authentication & Authorization
    ACCOUNT_LOCKED = auto()
    ACCOUNT_SUSPENDED = auto()
    ACCOUNT_EXPIRED = auto()
    TOKEN_EXPIRED = auto()
    TOKEN_INVALID = auto()
    INVALID_CREDENTIALS = auto()
    INSUFFICIENT_PERMISSIONS = auto()
    ACCESS_DENIED = auto()
    SESSION_EXPIRED = auto()

    # Business Logic Errors
    INSUFFICIENT_FUNDS = auto()
    DAILY_LIMIT_EXCEEDED = auto()
    MONTHLY_LIMIT_EXCEEDED = auto()
    TRANSACTION_LIMIT_EXCEEDED = auto()
    MERCHANT_UNAVAILABLE = auto()
    SUBSCRIPTION_REQUIRED = auto()
    SUBSCRIPTION_EXPIRED = auto()
    FEATURE_NOT_AVAILABLE = auto()
    QUOTA_EXCEEDED = auto()

    # System Status & Maintenance
    SYSTEM_MAINTENANCE = auto()
    SERVICE_UNAVAILABLE = auto()
    DATABASE_UNAVAILABLE = auto()
    EXTERNAL_SERVICE_ERROR = auto()
    RATE_LIMIT_EXCEEDED = auto()
    SERVER_OVERLOADED = auto()
    SCHEDULED_MAINTENANCE = auto()

    # Data Integrity & Conflicts
    DUPLICATE_ENTRY = auto()
    RESOURCE_CONFLICT = auto()
    CONCURRENT_MODIFICATION = auto()
    FOREIGN_KEY_CONSTRAINT = auto()
    UNIQUE_CONSTRAINT_VIOLATION = auto()

    # Payment & Billing
    PAYMENT_FAILED = auto()
    PAYMENT_DECLINED = auto()
    CARD_EXPIRED = auto()
    INSUFFICIENT_BALANCE = auto()
    BILLING_ADDRESS_REQUIRED = auto()

    # User Account & Profile
    EMAIL_NOT_VERIFIED = auto()
    PHONE_NOT_VERIFIED = auto()
    PROFILE_INCOMPLETE = auto()
    TWO_FACTOR_REQUIRED = auto()
    PASSWORD_RESET_REQUIRED = auto()

    # Content & Moderation
    CONTENT_INAPPROPRIATE = auto()
    CONTENT_FLAGGED = auto()
    CONTENT_UNDER_REVIEW = auto()
    COPYRIGHT_VIOLATION = auto()

    # File & Upload Errors
    UPLOAD_FAILED = auto()
    FILE_VIRUS_DETECTED = auto()
    STORAGE_QUOTA_EXCEEDED = auto()

    # Third-party Integration
    GOOGLE_SERVICE_ERROR = auto()
    FACEBOOK_SERVICE_ERROR = auto()
    APPLE_SERVICE_ERROR = auto()
    PAYMENT_GATEWAY_ERROR = auto()
    EMAIL_SERVICE_ERROR = auto()
    SMS_SERVICE_ERROR = auto()

    # Generic Errors
    VALIDATION_ERROR = auto()
    PROCESSING_ERROR = auto()
    TEMPORARY_ERROR = auto()
    UNKNOWN_ERROR = auto()

    # API & Request Errors
    REQUEST_TIMEOUT = auto()
    MALFORMED_REQUEST = auto()
    UNSUPPORTED_OPERATION = auto()
    DEPRECATED_ENDPOINT = auto()

    @DynamicClassAttribute
    def value(self) -> str:
        """Convert enum name to lowercase with underscores"""
        return self._name_.lower()

    @classmethod
    def from_string(cls, code_string: str) -> "GeneralErrorCode":
        """
        Convert a string code to GeneralErrorCode enum.
        If not found, returns UNKNOWN_ERROR as fallback.
        """
        # Try to find by value
        for code in cls:
            if code.value == code_string:
                return code

        # Fallback to UNKNOWN_ERROR
        return cls.UNKNOWN_ERROR
