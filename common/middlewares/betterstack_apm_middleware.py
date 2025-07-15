import time
import logging
import structlog
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve, Resolver404
from django.http import Http404

logger = structlog.get_logger(__name__)


class BetterStackAPMMiddleware(MiddlewareMixin):
    """
    Middleware to track APM metrics for BetterStack monitoring.
    Tracks request duration, response codes, endpoints, and errors.
    """

    def process_request(self, request):
        """Start timing the request."""
        request._betterstack_start_time = time.time()
        request._betterstack_method = request.method
        request._betterstack_path = request.path
        
        # Try to resolve the URL pattern name
        try:
            resolved = resolve(request.path)
            request._betterstack_endpoint = f"{resolved.namespace}:{resolved.url_name}" if resolved.namespace else resolved.url_name
            request._betterstack_view_name = resolved.view_name
        except Resolver404:
            request._betterstack_endpoint = "unknown"
            request._betterstack_view_name = "unknown"

    def process_response(self, request, response):
        """Log successful request metrics."""
        if hasattr(request, '_betterstack_start_time'):
            duration = time.time() - request._betterstack_start_time
            
            # Log APM metrics
            logger.info(
                "request_completed",
                method=getattr(request, '_betterstack_method', 'UNKNOWN'),
                path=getattr(request, '_betterstack_path', 'unknown'),
                endpoint=getattr(request, '_betterstack_endpoint', 'unknown'),
                view_name=getattr(request, '_betterstack_view_name', 'unknown'),
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
                response_size=len(response.content) if hasattr(response, 'content') else 0,
                user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                remote_addr=self._get_client_ip(request),
                request_id=getattr(request, '_betterstack_request_id', None),
            )
            
            # Log slow requests as warnings
            if duration > 2.0:  # Requests slower than 2 seconds
                logger.warning(
                    "slow_request",
                    method=getattr(request, '_betterstack_method', 'UNKNOWN'),
                    path=getattr(request, '_betterstack_path', 'unknown'),
                    endpoint=getattr(request, '_betterstack_endpoint', 'unknown'),
                    duration_ms=round(duration * 1000, 2),
                    user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None,
                )

        return response

    def process_exception(self, request, exception):
        """Log exceptions and errors."""
        if hasattr(request, '_betterstack_start_time'):
            duration = time.time() - request._betterstack_start_time
            
            # Determine error type and status code
            if isinstance(exception, Http404):
                status_code = 404
                error_type = "Http404"
            else:
                status_code = 500
                error_type = exception.__class__.__name__
            
            logger.error(
                "request_error",
                method=getattr(request, '_betterstack_method', 'UNKNOWN'),
                path=getattr(request, '_betterstack_path', 'unknown'),
                endpoint=getattr(request, '_betterstack_endpoint', 'unknown'),
                view_name=getattr(request, '_betterstack_view_name', 'unknown'),
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
                error_type=error_type,
                error_message=str(exception),
                user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                remote_addr=self._get_client_ip(request),
                exc_info=True,
            )

    def _get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip 