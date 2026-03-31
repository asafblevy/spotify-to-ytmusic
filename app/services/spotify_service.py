import time
import spotipy
from app.models import Track, Playlist, Artist


def _parse_track(item: dict) -> Track | None:
    track = item.get("track") or item
    if not track or not track.get("id"):
        return None
    artists = [a["name"] for a in track.get("artists", [])]
    return Track(
        spotify_id=track["id"],
        title=track["name"],
        artist=artists[0] if artists else "Unknown",
        all_artists=artists,
        album=track.get("album", {}).get("name", ""),
        duration_ms=track.get("duration_ms", 0),
    )


def fetch_liked_songs(sp: spotipy.Spotify) -> list[Track]:
    tracks = []
    results = sp.current_user_saved_tracks(limit=50)
    while results:
        for item in results["items"]:
            t = _parse_track(item)
            if t:
                tracks.append(t)
        if results["next"]:
            time.sleep(0.1)
            results = sp.next(results)
        else:
            break
    return tracks


def fetch_playlists(sp: spotipy.Spotify, on_progress=None) -> tuple[list[Playlist], list[str]]:
    playlists = []
    skipped = []
    # First pass: get all playlist metadata
    all_items = []
    results = sp.current_user_playlists(limit=50)
    while results:
        all_items.extend(results["items"])
        if results["next"]:
            results = sp.next(results)
        else:
            break

    total = len(all_items)
    for i, item in enumerate(all_items):
        pid = item["id"]
        name = item["name"]
        if on_progress:
            on_progress(f"Fetching playlist {i + 1}/{total}: {name}")
        try:
            tracks = []
            pitems = sp.playlist_items(pid, limit=100)
            while pitems:
                for pitem in pitems["items"]:
                    t = _parse_track(pitem)
                    if t:
                        tracks.append(t)
                if pitems["next"]:
                    time.sleep(0.1)
                    pitems = sp.next(pitems)
                else:
                    break
            playlists.append(Playlist(spotify_id=pid, name=name, tracks=tracks))
        except Exception:
            skipped.append(name)
        time.sleep(0.1)
    return playlists, skipped


def fetch_followed_artists(sp: spotipy.Spotify) -> list[Artist]:
    artists = []
    results = sp.current_user_followed_artists(limit=50)
    while results and results.get("artists"):
        for item in results["artists"]["items"]:
            artists.append(Artist(spotify_id=item["id"], name=item["name"]))
        cursors = results["artists"].get("cursors") or {}
        after = cursors.get("after") or (
            results["artists"]["items"][-1]["id"]
            if results["artists"]["items"]
            else None
        )
        if after and results["artists"].get("next"):
            time.sleep(0.1)
            results = sp.current_user_followed_artists(limit=50, after=after)
        else:
            break
    return artists
