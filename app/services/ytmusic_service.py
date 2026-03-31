import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import settings


def _get_youtube(session: dict):
    """Build YouTube Data API client from user's OAuth token."""
    token = session.get("ytmusic_token", {})
    creds = Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return build("youtube", "v3", credentials=creds)


def like_songs(session: dict, video_ids: list[str], delay: float = 0.3) -> int:
    """Rate videos as 'like'. Returns count of successful likes."""
    youtube = _get_youtube(session)
    liked = 0
    for vid in video_ids:
        try:
            youtube.videos().rate(id=vid, rating="like").execute()
            liked += 1
        except Exception:
            pass
        time.sleep(delay)
    return liked


def create_playlist(session: dict, name: str, video_ids: list[str]) -> str | None:
    """Create a playlist and add tracks. Returns playlist ID."""
    if not video_ids:
        return None
    youtube = _get_youtube(session)
    try:
        # Create playlist
        pl = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": name,
                    "description": "Transferred from Spotify",
                },
                "status": {"privacyStatus": "private"},
            },
        ).execute()
        playlist_id = pl["id"]

        # Add videos
        for vid in video_ids:
            try:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": vid,
                            },
                        },
                    },
                ).execute()
            except Exception:
                pass
            time.sleep(0.1)

        return playlist_id
    except Exception:
        return None


def subscribe_artist(session: dict, artist_name: str) -> bool:
    """Search for an artist's channel and subscribe. Returns True on success."""
    youtube = _get_youtube(session)
    try:
        # Search for the artist's channel
        results = youtube.search().list(
            q=artist_name, part="snippet", type="channel", maxResults=1
        ).execute()
        items = results.get("items", [])
        if not items:
            return False
        channel_id = items[0]["snippet"]["channelId"]

        # Subscribe
        youtube.subscriptions().insert(
            part="snippet",
            body={
                "snippet": {
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": channel_id,
                    },
                },
            },
        ).execute()
        return True
    except Exception:
        return False
