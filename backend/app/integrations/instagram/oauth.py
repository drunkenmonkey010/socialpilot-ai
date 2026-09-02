from urllib.parse import urlencode

from app.core.config import settings


INSTAGRAM_AUTH_URL = "https://www.facebook.com/v24.0/dialog/oauth"


def get_instagram_authorization_url(
    state: str,
) -> str:
    params = {
        "client_id": settings.instagram_app_id,
        "redirect_uri": settings.instagram_redirect_uri,
        "state": state,
        "scope": (
            "instagram_basic,"
            "instagram_content_publish,"
            "pages_show_list,"
            "pages_read_engagement"
        ),
        "response_type": "code",
    }

    return f"{INSTAGRAM_AUTH_URL}?{urlencode(params)}"