import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
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
    state.update({
        "phase": "Starting...",
        "total": 0,
        "processed": 0,
        "liked": 0,
        "failed": 0,
        "done": False,
        "error": None,
        "log": [],
    })

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

        state["total"] = len(videos)
        state["log"].append(f"Found {len(videos)} tracks")

        # Deduplicate
        seen = set()
        unique = []
        for v in videos:
            if v["videoId"] not in seen:
                seen.add(v["videoId"])
                unique.append(v)
        if len(unique) < len(videos):
            state["log"].append(f"Skipping {len(videos) - len(unique)} duplicates")
            state["total"] = len(unique)

        # Like each video
        state["phase"] = "Liking songs..."
        for i, v in enumerate(unique):
            state["phase"] = f"Liking ({i+1}/{len(unique)}): {v['title']}"
            state["processed"] = i + 1
            try:
                youtube.videos().rate(id=v["videoId"], rating="like").execute()
                state["liked"] += 1
            except Exception as e:
                state["failed"] += 1
                if state["failed"] <= 10:
                    state["log"].append(f"Failed: {v['title']} ({e})")
            time.sleep(0.15)

        state["phase"] = "Complete!"
        state["done"] = True
        state["log"].append(f"Done! Liked {state['liked']}/{len(unique)} songs. {state['failed']} failed.")

    except Exception as e:
        import traceback
        state["error"] = f"{type(e).__name__}: {e}"
        state["log"].append(f"ERROR: {e}")
        state["log"].append(traceback.format_exc())
        state["done"] = True
