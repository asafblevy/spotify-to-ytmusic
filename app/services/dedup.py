import time
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import settings


def _get_youtube_oauth(session: dict):
    """Build a YouTube Data API client using the user's OAuth token."""
    token = session.get("ytmusic_token", {})
    creds = Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return build("youtube", "v3", credentials=creds)


def _get_youtube_api_key():
    """Build a YouTube Data API client using API key (for read-only ops)."""
    return build("youtube", "v3", developerKey=settings.google_api_key)


def _get_all_playlists(youtube) -> list[dict]:
    """Fetch all user's playlists via YouTube Data API."""
    playlists = []
    request = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
    while request:
        response = request.execute()
        for item in response.get("items", []):
            playlists.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
            })
        request = youtube.playlists().list_next(request, response)
    return playlists


def _get_playlist_items(youtube, playlist_id: str) -> list[dict]:
    """Fetch all items in a playlist."""
    items = []
    request = youtube.playlistItems().list(
        part="snippet,contentDetails", playlistId=playlist_id, maxResults=50
    )
    while request:
        response = request.execute()
        for item in response.get("items", []):
            items.append({
                "id": item["id"],  # playlistItem ID (needed for deletion)
                "videoId": item["contentDetails"]["videoId"],
                "title": item["snippet"].get("title", ""),
            })
        request = youtube.playlistItems().list_next(request, response)
    return items


def run_dedup(session: dict) -> None:
    """Go over all YouTube Music playlists and remove duplicate tracks."""
    state = session["dedup_state"]
    state.update({
        "phase": "Starting...",
        "total_playlists": 0,
        "processed_playlists": 0,
        "total_removed": 0,
        "done": False,
        "error": None,
        "log": ["Starting dedup..."],
    })

    try:
        # Use OAuth client (needed for both reading own playlists and deleting items)
        state["log"].append("Connecting to YouTube...")
        youtube = _get_youtube_oauth(session)

        # Fetch all playlists
        state["phase"] = "Fetching your playlists..."
        state["log"].append("Fetching playlists...")
        playlists = _get_all_playlists(youtube)
        state["total_playlists"] = len(playlists)
        state["log"].append(f"Found {len(playlists)} playlists")

        for i, pl in enumerate(playlists):
            pl_id = pl["id"]
            pl_title = pl["title"]
            state["phase"] = f"Checking ({i+1}/{len(playlists)}): {pl_title}"
            state["processed_playlists"] = i + 1

            try:
                items = _get_playlist_items(youtube, pl_id)

                if not items:
                    continue

                # Find duplicates by videoId
                seen = set()
                dupes = []
                for item in items:
                    vid = item["videoId"]
                    if vid in seen:
                        dupes.append(item)
                    else:
                        seen.add(vid)

                if dupes:
                    state["log"].append(
                        f"{pl_title}: removing {len(dupes)} duplicates "
                        f"(keeping {len(seen)}/{len(items)})"
                    )
                    for dupe in dupes:
                        try:
                            youtube.playlistItems().delete(id=dupe["id"]).execute()
                            state["total_removed"] += 1
                        except Exception as e:
                            state["log"].append(f"  Failed to remove '{dupe['title']}': {e}")
                        time.sleep(0.2)

            except Exception as e:
                state["log"].append(f"  Skipped {pl_title}: {type(e).__name__}: {e}")

            time.sleep(0.3)

        state["phase"] = "Complete!"
        state["done"] = True
        state["log"].append(
            f"Done! Removed {state['total_removed']} duplicates "
            f"across {state['total_playlists']} playlists."
        )

    except Exception as e:
        import traceback
        state["error"] = f"{type(e).__name__}: {e}"
        state["log"].append(f"ERROR: {e}")
        state["log"].append(traceback.format_exc())
        state["done"] = True
