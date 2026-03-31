import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.config import settings


def _get_youtube(session: dict):
    token = session.get("ytmusic_token", {})
    creds = Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return build("youtube", "v3", credentials=creds)


def get_playlists(session: dict) -> list[dict]:
    youtube = _get_youtube(session)
    playlists = []
    request = youtube.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50)
    while request:
        response = request.execute()
        for item in response.get("items", []):
            playlists.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
                "count": item["contentDetails"]["itemCount"],
            })
        request = youtube.playlists().list_next(request, response)
    return playlists


def run_bulk_like(session: dict, playlist_id: str) -> None:
    state = session["bulk_like_state"]
    # Check if resuming from a previous run
    previously_liked = set(state.get("already_liked_ids", []))
    resuming = len(previously_liked) > 0

    state.update({
        "phase": "Starting...",
        "total": 0,
        "processed": 0,
        "liked": 0,
        "skipped": 0,
        "failed": 0,
        "quota_hit": False,
        "done": False,
        "error": None,
        "log": [],
        "already_liked_ids": list(previously_liked),
        "playlist_id": playlist_id,
    })

    if resuming:
        state["log"].append(f"Resuming — {len(previously_liked)} songs already liked, skipping those")

    try:
        youtube = _get_youtube(session)

        # Fetch all videos in the playlist
        state["phase"] = "Fetching playlist tracks..."
        state["log"].append("Fetching playlist tracks...")
        videos = []
        request = youtube.playlistItems().list(
            part="snippet,contentDetails", playlistId=playlist_id, maxResults=50
        )
        while request:
            response = request.execute()
            for item in response.get("items", []):
                videos.append({
                    "videoId": item["contentDetails"]["videoId"],
                    "title": item["snippet"].get("title", "Unknown"),
                })
            request = youtube.playlistItems().list_next(request, response)

        # Deduplicate
        seen = set()
        unique = []
        for v in videos:
            if v["videoId"] not in seen:
                seen.add(v["videoId"])
                unique.append(v)

        # Filter out already liked (from previous run)
        remaining = [v for v in unique if v["videoId"] not in previously_liked]

        state["total"] = len(remaining)
        state["log"].append(f"Found {len(videos)} tracks ({len(unique)} unique, {len(remaining)} to like)")

        if not remaining:
            state["phase"] = "Complete!"
            state["done"] = True
            state["log"].append("All songs already liked!")
            return

        # Like each video
        state["phase"] = "Liking songs..."
        for i, v in enumerate(remaining):
            state["phase"] = f"Liking ({i+1}/{len(remaining)}): {v['title']}"
            state["processed"] = i + 1
            try:
                youtube.videos().rate(id=v["videoId"], rating="like").execute()
                state["liked"] += 1
                state["already_liked_ids"].append(v["videoId"])
            except HttpError as e:
                if "quotaExceeded" in str(e):
                    state["quota_hit"] = True
                    state["log"].append(
                        f"Quota limit reached after {state['liked']} likes. "
                        f"{len(remaining) - i - 1} songs remaining. "
                        f"Quota resets at midnight Pacific Time — come back and hit Resume."
                    )
                    break
                state["failed"] += 1
                if state["failed"] <= 10:
                    state["log"].append(f"Failed: {v['title']} ({e})")
            except Exception as e:
                state["failed"] += 1
                if state["failed"] <= 10:
                    state["log"].append(f"Failed: {v['title']} ({e})")
            time.sleep(0.15)

        if state["quota_hit"]:
            state["phase"] = "Paused — quota limit reached"
        else:
            state["phase"] = "Complete!"
        state["done"] = True

        total_liked = len(state["already_liked_ids"])
        state["log"].append(
            f"{'Paused' if state['quota_hit'] else 'Done'}! "
            f"Liked {total_liked}/{len(unique)} total songs. "
            f"{state['failed']} failed."
        )

    except Exception as e:
        import traceback
        state["error"] = f"{type(e).__name__}: {e}"
        state["log"].append(f"ERROR: {e}")
        state["log"].append(traceback.format_exc())
        state["done"] = True
