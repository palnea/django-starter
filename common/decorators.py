from functools import wraps
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from common.templates.swagger.passcode import passcode_form

def swagger_passcode_required(view_func):
    """
    Decorator for views that checks that the user has entered the swagger passcode.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.session.get("has_swagger_access", False):
            if (
                request.method == "POST"
                and request.POST.get("passcode") == settings.SWAGGER_ACCESS_PASSCODE
            ):
                request.session["has_swagger_access"] = True
                return redirect(request.path)
            return HttpResponse(passcode_form, status=401)
        return view_func(request, *args, **kwargs)
    return _wrapped_view
