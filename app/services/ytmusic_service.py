import time
from ytmusicapi import YTMusic


def like_songs(yt: YTMusic, video_ids: list[str], delay: float = 0.3) -> int:
    """Rate songs as LIKE. Returns count of successful likes."""
    liked = 0
    for vid in video_ids:
        try:
            yt.rate_song(vid, "LIKE")
            liked += 1
        except Exception:
            pass
        time.sleep(delay)
    return liked


def create_playlist(yt: YTMusic, name: str, video_ids: list[str]) -> str | None:
    """Create a playlist and add tracks. Returns playlist ID."""
    if not video_ids:
        return None
    try:
        # Create with first batch
        first_batch = video_ids[:150]
        playlist_id = yt.create_playlist(
            title=name,
            description="Transferred from Spotify",
            video_ids=first_batch,
        )
        # Add remaining in batches
        remaining = video_ids[150:]
        while remaining:
            batch = remaining[:50]
            remaining = remaining[50:]
            try:
                yt.add_playlist_items(playlist_id, batch)
            except Exception:
                pass
            time.sleep(0.5)
        return playlist_id
    except Exception:
        return None


def subscribe_artist(yt: YTMusic, artist_name: str) -> bool:
    """Search for an artist and subscribe. Returns True on success."""
    try:
        results = yt.search(artist_name, filter="artists", limit=1)
        if results and results[0].get("browseId"):
            yt.subscribe_artists([results[0]["browseId"]])
            return True
    except Exception:
        pass
    return False
