from enum import Enum

from django.conf import settings
from environ import Env


class Environment(Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


ENVIRONMENT_MAPPER = {
    "dev": Environment.DEVELOPMENT,
    "prod": Environment.PRODUCTION,
    "local": Environment.DEVELOPMENT,
    "development": Environment.DEVELOPMENT,
    "test": Environment.TEST,
    "staging": Environment.STAGING,
    "production": Environment.PRODUCTION,
}

EXTENSION_MAPPER = {"png": "png", "jpeg": "jpeg", "svg+xml": "svg"}


def get_env_file() -> Env:
    return settings.ENV


def get_environment_variable(key, default=None):
    env = get_env_file()
    return env.get_value(key, default=default)


def get_environment(env_file=None) -> str:
    try:
        env = get_env_file() if not env_file else env_file
        return str(
            ENVIRONMENT_MAPPER.get(
                str(env.get_value("ENV", default=None)), Environment.DEVELOPMENT
            ).value
        )
    except Exception:
        return Environment.DEVELOPMENT.value
