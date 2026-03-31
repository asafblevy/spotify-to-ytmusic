import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import MemoryCacheHandler
from app.config import settings

SCOPES = "user-library-read playlist-read-private playlist-read-collaborative user-follow-read"


def get_spotify_oauth(session: dict) -> SpotifyOAuth:
    cache = MemoryCacheHandler(token_info=session.get("spotify_token"))
    oauth = SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=f"{settings.base_url}/auth/spotify/callback",
        scope=SCOPES,
        cache_handler=cache,
    )
    return oauth


def get_spotify_client(session: dict) -> spotipy.Spotify | None:
    token_info = session.get("spotify_token")
    if not token_info:
        return None
    oauth = get_spotify_oauth(session)
    # Refresh if needed
    if oauth.is_token_expired(token_info):
        token_info = oauth.refresh_access_token(token_info["refresh_token"])
        session["spotify_token"] = token_info
    return spotipy.Spotify(auth=token_info["access_token"])
