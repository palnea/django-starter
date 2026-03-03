from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """
    Rate throttle for authentication endpoints (login, register, password reset,
    social auth). Uses the 'auth' rate from DEFAULT_THROTTLE_RATES.

    This throttle is keyed by IP address (via AnonRateThrottle) so that
    unauthenticated brute-force attempts are limited regardless of whether
    the request includes valid credentials.
    """

    scope = "auth"
