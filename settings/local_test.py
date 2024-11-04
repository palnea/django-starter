from settings.development import *

VERIFICATION_ACTIVE_INTERVAL = 300

INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in ["logger"]]
