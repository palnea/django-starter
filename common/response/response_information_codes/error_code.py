from enum import Enum, auto
from types import DynamicClassAttribute


class ErrorCode(Enum):
    CONTACT_NOT_VERIFIED = auto()
    GOOGLE_PLAY_CONSOLE_CREDENTIALS_NOT_FOUND = auto()
    PROVIDED_CODE_IS_NOT_APPLICABLE = auto()
    PROVIDED_CODE_IS_WRONG = auto()
    INTEGRITY_ERROR = auto()
    DUPLICATE_KEY_ERROR = auto()
    DUPLICATE_REQUEST = auto()
    VERIFICATION_PREREQUISITE_NOT_SATISFIED = auto()
    INVALID_RECEIPT = auto()
    EMPTY_OR_NULL_RECEIPT = auto()
    ACTIVE_SUBSCRIPTION_EXISTS = auto()
    NOT_ENOUGH_BALANCE_LEFT = auto()
    PASSWORD_DOES_NOT_MATCH = auto()
    PASSWORD_NOT_PROVIDED = auto()
    UNKNOWN_ERROR = auto()
    GENERAL_VALIDATION_ERROR = auto()
    INTERNAL_SERVER_ERROR = auto()
    NOT_FOUND_ERROR = auto()
    INVALID_INPUT = auto()
    PERMISSION_DENIED = auto()
    VIEW_DOESNT_EXIST = auto()
    MIDDLEWARE_NOT_USED = auto()
    IMPROPERLY_CONFIGURED = auto()
    FIELD_ERROR = auto()
    BAD_REQUEST = auto()
    TRANSACTION_MANAGEMENT_ERROR = auto()
    SESSION_INTERRUPTED = auto()
    FILE_UNREADABLE = auto()
    REQUEST_ABORTED = auto()
    THROTTLED = auto()
    UNSUPPORTED_MEDIA_TYPE = auto()
    NOT_ACCEPTABLE = auto()
    METHOD_NOT_ALLOWED = auto()
    NOT_AUTHENTICATED = auto()
    AUTHENTICATION_FAILED = auto()
    PARSE_ERROR = auto()
    INVALID_TOKEN = auto()
    FAILED_TO_SEND_MESSAGE = auto()
    AN_ERROR_OCCURED = auto()

    @DynamicClassAttribute
    def value(self) -> str:
        """The value of the Enum member."""
        return "ERR_" + str(self._name_)
