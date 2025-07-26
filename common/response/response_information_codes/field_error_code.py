from enum import Enum, auto
from types import DynamicClassAttribute


class FieldErrorCode(Enum):
    """
    Standardized codes for field-level validation errors.
    These codes are used in the 'errors' section of structured error responses.
    """

    # Generic validation codes
    REQUIRED = auto()
    INVALID = auto()
    INVALID_FORMAT = auto()
    INVALID_CHOICE = auto()
    NULL = auto()
    BLANK = auto()

    # String validation codes
    TOO_SHORT = auto()
    TOO_LONG = auto()
    MIN_LENGTH = auto()
    MAX_LENGTH = auto()

    # Email validation codes
    INVALID_EMAIL = auto()
    EMAIL_ALREADY_EXISTS = auto()

    # Password validation codes
    PASSWORD_TOO_SHORT = auto()
    PASSWORD_TOO_WEAK = auto()
    PASSWORD_TOO_COMMON = auto()
    PASSWORD_NUMERIC = auto()
    PASSWORD_MISMATCH = auto()

    # Numeric validation codes
    MIN_VALUE = auto()
    MAX_VALUE = auto()
    DECIMAL_PLACES = auto()
    MAX_DIGITS = auto()
    INVALID_INTEGER = auto()
    INVALID_NUMBER = auto()

    # Date/Time validation codes
    INVALID_DATE = auto()
    INVALID_DATETIME = auto()
    INVALID_TIME = auto()
    DATE_IN_PAST = auto()
    DATE_IN_FUTURE = auto()

    # File validation codes
    INVALID_FILE_TYPE = auto()
    FILE_TOO_LARGE = auto()
    FILE_EMPTY = auto()
    INVALID_IMAGE = auto()

    # URL validation codes
    INVALID_URL = auto()

    # Phone validation codes
    INVALID_PHONE = auto()
    PHONE_ALREADY_EXISTS = auto()

    # Custom business validation codes
    USERNAME_TAKEN = auto()
    USERNAME_RESERVED = auto()
    INVALID_USERNAME = auto()
    INVALID_POSTAL_CODE = auto()
    AGE_TOO_YOUNG = auto()
    AGE_TOO_OLD = auto()

    # Relationship validation codes
    DOES_NOT_EXIST = auto()
    ALREADY_EXISTS = auto()
    PERMISSION_DENIED = auto()
    FOREIGN_KEY_VIOLATION = auto()

    # Boolean validation codes
    INVALID_BOOLEAN = auto()

    # List/Array validation codes
    EMPTY_LIST = auto()
    INVALID_LIST = auto()

    # JSON validation codes
    INVALID_JSON = auto()

    # Custom domain validation codes
    TEST_EMAIL_FORBIDDEN = auto()
    DOMAIN_NOT_ALLOWED = auto()

    @DynamicClassAttribute
    def value(self) -> str:
        """Convert enum name to lowercase with underscores"""
        return self._name_.lower()

    @classmethod
    def get_drf_mapping(cls) -> dict:
        """
        Mapping from DRF default error codes to our FieldErrorCode enum.
        This helps convert DRF validation errors to structured codes.
        """
        return {
            "required": cls.REQUIRED,
            "invalid": cls.INVALID,
            "invalid_choice": cls.INVALID_CHOICE,
            "blank": cls.BLANK,
            "null": cls.NULL,
            "min_length": cls.MIN_LENGTH,
            "max_length": cls.MAX_LENGTH,
            "min_value": cls.MIN_VALUE,
            "max_value": cls.MAX_VALUE,
            "invalid_email": cls.INVALID_EMAIL,
            "invalid_url": cls.INVALID_URL,
            "invalid_date": cls.INVALID_DATE,
            "invalid_datetime": cls.INVALID_DATETIME,
            "invalid_time": cls.INVALID_TIME,
            "invalid_image": cls.INVALID_IMAGE,
            "decimal_places": cls.DECIMAL_PLACES,
            "max_digits": cls.MAX_DIGITS,
            "invalid_integer": cls.INVALID_INTEGER,
            # Custom mappings for our application
            "too_short": cls.TOO_SHORT,
            "too_long": cls.TOO_LONG,
            "invalid_format": cls.INVALID_FORMAT,
            "test_email_forbidden": cls.TEST_EMAIL_FORBIDDEN,
            "reserved_username": cls.USERNAME_RESERVED,
        }

    @classmethod
    def from_string(cls, code_string: str) -> "FieldErrorCode":
        """
        Convert a string code to FieldErrorCode enum.
        If not found, returns INVALID as fallback.
        """
        # Try direct mapping first
        drf_mapping = cls.get_drf_mapping()
        if code_string in drf_mapping:
            return drf_mapping[code_string]

        # Try to find by value
        for code in cls:
            if code.value == code_string:
                return code

        # Fallback to INVALID
        return cls.INVALID
