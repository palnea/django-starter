import concurrent.futures

import httpx
import newrelic.agent
from django.conf import settings as django_settings

executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)


def send_to_newrelic(logger, log_method, event_dict):
    # Set parameters
    settings = newrelic.agent.application_settings()
    if settings is None:
        if django_settings.DEBUG:
            print(
                {
                    "message": f"{event_dict['event']}",
                    "attributes": event_dict,
                    "level": log_method.upper(),
                }
            )
        return

    license_key = settings.license_key
    headers = {"Api-Key": license_key}

    entity_guid = ""
    if settings and settings.entity_guid:
        entity_guid = settings.entity_guid

    # Our log message and all the event context is sent as a JSON string
    # in the POST body
    # https://docs.newrelic.com/docs/logs/log-management/log-api/introduc   tion-log-api/#json-content
    payload = {
        "message": f"{event_dict['event']}",
        "attributes": event_dict,
        "entity": {"name": newrelic.agent.application().name, "guid": entity_guid},
        "level": log_method.upper(),
    }

    transport = httpx.HTTPTransport(retries=5)
    limits = httpx.Limits(
        max_keepalive_connections=20, max_connections=100, keepalive_expiry=5
    )
    client = httpx.Client(limits=limits, transport=transport)

    executor.submit(send_request, client, payload, headers)

    return event_dict


def send_request(client, payload, headers):
    if django_settings.DEBUG:
        print(payload)
    else:
        _response = client.post(
            "https://log-api.eu.newrelic.com/log/v1", json=payload, headers=headers
        )
