from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.urls import reverse


class SessionSecurityMiddleware:
    """Prevent private pages from being cached and label stale-session redirects."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            response.headers["Cache-Control"] = "private, no-store, no-cache, max-age=0, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif (
            request.path != reverse("logout")
            and settings.SESSION_COOKIE_NAME in request.COOKIES
            and response.status_code in (301, 302, 303, 307, 308)
        ):
            parts = urlsplit(response.headers.get("Location", ""))
            if parts.path == reverse("login"):
                query = parse_qsl(parts.query, keep_blank_values=True)
                if not any(key == "session_expired" for key, _ in query):
                    query.append(("session_expired", "1"))
                    response.headers["Location"] = urlunsplit(
                        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
                    )

        return response
