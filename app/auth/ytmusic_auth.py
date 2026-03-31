from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials
from app.config import settings

_TOKEN_KEYS = {"scope", "token_type", "access_token", "refresh_token", "expires_at", "expires_in"}


def get_oauth_credentials() -> OAuthCredentials:
    return OAuthCredentials(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def start_device_flow() -> dict:
    """Start the Google device code flow. Returns device_code, user_code, verification_url."""
    creds = get_oauth_credentials()
    code_info = creds.get_code()
    return code_info


def poll_device_flow(device_code: str) -> dict | None:
    """Poll for device code completion. Returns token dict on success, None if still pending."""
    creds = get_oauth_credentials()
    try:
        token = creds.token_from_code(device_code)
        # Google returns {"error": "authorization_pending"} while user hasn't authorized yet.
        # token_from_code doesn't raise — it just returns the error JSON.
        if not token or "error" in token or "access_token" not in token:
            return None
        return token
    except Exception:
        return None


def get_ytmusic_client(session: dict) -> YTMusic | None:
    token = session.get("ytmusic_token")
    if not token or "access_token" not in token:
        return None
    creds = get_oauth_credentials()
    # Only pass keys that RefreshingToken accepts
    clean = {k: v for k, v in token.items() if k in _TOKEN_KEYS}
    return YTMusic(auth=clean, oauth_credentials=creds)
