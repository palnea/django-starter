import concurrent.futures
import os

import httpx
from django.conf import settings as django_settings

executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)


def send_to_betterstack(logger, log_method, event_dict):
    """
    BetterStack (Logtail) logging processor for structlog.
    Sends logs to BetterStack for monitoring and analysis.
    """
    # Get BetterStack source token from environment
    source_token = os.environ.get('BETTERSTACK_SOURCE_TOKEN')
    if not source_token:
        if django_settings.DEBUG:
            print(
                {
                    "message": f"{event_dict['event']}",
                    "attributes": event_dict,
                    "level": log_method.upper(),
                }
            )
        return event_dict

    # Prepare the log payload for BetterStack
    payload = {
        "message": f"{event_dict['event']}",
        "level": log_method.upper(),
        "timestamp": event_dict.get('timestamp'),
        **event_dict  # Include all structured data
    }

    # BetterStack ingesting endpoint
    headers = {
        "Authorization": f"Bearer {source_token}",
        "Content-Type": "application/json"
    }

    # Send to BetterStack asynchronously
    executor.submit(send_request_to_betterstack, payload, headers)

    return event_dict


def send_request_to_betterstack(payload, headers):
    """Send log data to BetterStack API."""
    if django_settings.DEBUG:
        print("BetterStack log:", payload)
    else:
        try:
            transport = httpx.HTTPTransport(retries=3)
            limits = httpx.Limits(
                max_keepalive_connections=20, 
                max_connections=100, 
                keepalive_expiry=5
            )
            client = httpx.Client(limits=limits, transport=transport)
            
            # BetterStack log ingestion endpoint
            response = client.post(
                "https://in.logs.betterstack.com/",
                json=payload,
                headers=headers,
                timeout=5.0
            )
            response.raise_for_status()
        except Exception as e:
            # Log errors to console in production but don't fail the request
            print(f"Failed to send log to BetterStack: {e}")
        finally:
            try:
                client.close()
            except:
                pass
