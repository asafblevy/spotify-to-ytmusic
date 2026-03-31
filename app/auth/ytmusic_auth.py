from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials
from app.config import settings


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
        return token
    except Exception:
        return None


_TOKEN_KEYS = {"scope", "token_type", "access_token", "refresh_token", "expires_at", "expires_in"}


def _clean_token(token: dict) -> dict:
    """Keep only the keys that RefreshingToken accepts."""
    return {k: v for k, v in token.items() if k in _TOKEN_KEYS}


def get_ytmusic_client(session: dict) -> YTMusic | None:
    token = session.get("ytmusic_token")
    if not token:
        return None
    creds = get_oauth_credentials()
    return YTMusic(auth=_clean_token(token), oauth_credentials=creds)
