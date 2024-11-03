from structlog import get_logger

import facebook

log = get_logger(__name__)


class Facebook:
    """
    Facebook class to fetch the user info and return it
    """

    @staticmethod
    def validate(auth_token):
        """
        validate method Queries the facebook GraphAPI to fetch the user info
        """
        try:
            graph = facebook.GraphAPI(access_token=auth_token)
            profile = graph.request("/me?fields=name,email")
            return profile
        except Exception as e:
            log.info(
                "Social auth validation failure.", provider="facebook", exception=str(e)
            )
            return "The token is invalid or expired."
