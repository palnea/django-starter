from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from common.templates.swagger.passcode import passcode_form


class SwaggerAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # URLs to protect
        protected_urls = [reverse("schema-swagger-ui"), reverse("schema-redoc")]

        # Check if the request path is one of the protected URLs
        if any(url in request.path for url in protected_urls):
            # Check if the passcode is in the session
            if not request.session.get("has_swagger_access", False):
                # If it's a POST request, validate the passcode
                if (
                    request.method == "POST"
                    and request.POST.get("passcode") == settings.SWAGGER_ACCESS_PASSCODE
                ):
                    request.session["has_swagger_access"] = True
                    return redirect(request.path)
                # For GET or failed POST, show the passcode form
                return HttpResponse(passcode_form, status=401)

        return self.get_response(request)
