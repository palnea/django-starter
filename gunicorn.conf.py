import os
from utils.constants.environment_variables import get_environment


def post_fork(server, worker):
    """
    Post-fork hook for Gunicorn workers.
    BetterStack doesn't require agent initialization like New Relic.
    Just ensure environment variables are available.
    """
    environment = get_environment()
    
    # Ensure BetterStack token is available
    betterstack_token = os.environ.get('BETTERSTACK_SOURCE_TOKEN')
    if not betterstack_token:
        print(f"Warning: BETTERSTACK_SOURCE_TOKEN not set for {environment} environment")
    else:
        print(f"BetterStack logging configured for {environment} environment")
