import newrelic.agent

from utils.constants.environment_variables import get_environment


def post_fork(server, worker):
    environment = get_environment()
    newrelic_config_file = "settings/logger/" + environment + ".ini"
    newrelic.agent.initialize(newrelic_config_file)
    newrelic.agent.register_application(timeout=10.0)
