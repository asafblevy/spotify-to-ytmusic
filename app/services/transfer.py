import asyncio
import time
from app.models import Track, MatchResult
from app.services import matcher, ytmusic_service
from app.auth.spotify_auth import get_spotify_client
from app.auth.ytmusic_auth import get_ytmusic_client
from app.services.spotify_service import (
    fetch_liked_songs,
    fetch_playlists,
    fetch_followed_artists,
)


def run_transfer(session: dict, options: dict) -> None:
    """Run the full transfer. Updates session['transfer_state'] as it goes."""
    state = session.setdefault("transfer_state", {})
    state.update(
        {
            "phase": "starting",
            "total": 0,
            "processed": 0,
            "matched": 0,
            "failed_tracks": [],
            "done": False,
            "error": None,
            "log": [],
        }
    )

    try:
        sp = get_spotify_client(session)
        yt = get_ytmusic_client(session)
        if not sp or not yt:
            state["error"] = "Not authenticated with both services"
            state["done"] = True
            return

        # Phase 1: Fetch Spotify data
        liked = []
        playlists = []
        artists = []

        if options.get("liked_songs"):
            state["phase"] = "Fetching liked songs from Spotify..."
            state["log"].append("Fetching liked songs...")
            liked = fetch_liked_songs(sp)
            state["log"].append(f"Found {len(liked)} liked songs")

        if options.get("playlists"):
            state["phase"] = "Fetching playlists from Spotify..."
            state["log"].append("Fetching playlists...")
            # Re-auth in case token expired during fetch
            sp = get_spotify_client(session)
            playlists = fetch_playlists(sp)
            state["log"].append(
                f"Found {len(playlists)} playlists "
                f"({sum(len(p.tracks) for p in playlists)} total tracks)"
            )

        if options.get("artists"):
            state["phase"] = "Fetching followed artists from Spotify..."
            state["log"].append("Fetching artists...")
            sp = get_spotify_client(session)
            artists = fetch_followed_artists(sp)
            state["log"].append(f"Found {len(artists)} followed artists")

        # Build unique track set for matching
        all_tracks: dict[str, Track] = {}
        for t in liked:
            all_tracks[t.spotify_id] = t
        for p in playlists:
            for t in p.tracks:
                all_tracks[t.spotify_id] = t

        state["total"] = len(all_tracks) + len(artists)
        state["processed"] = 0

        # Phase 2: Match tracks
        state["phase"] = "Matching songs on YouTube Music..."
        match_cache: dict[str, str | None] = {}  # spotify_id -> videoId

        for sid, track in all_tracks.items():
            state["phase"] = f"Matching: {track.artist} - {track.title}"
            video_id, score = matcher.find_match(yt, track)
            match_cache[sid] = video_id
            state["processed"] += 1
            if video_id:
                state["matched"] += 1
            else:
                state["failed_tracks"].append(
                    f"{track.artist} - {track.title} (score: {score:.0f})"
                )
            time.sleep(0.4)

        # Phase 3: Transfer liked songs
        if options.get("liked_songs") and liked:
            state["phase"] = "Liking songs on YouTube Music..."
            state["log"].append("Liking songs on YouTube Music...")
            liked_ids = [
                match_cache[t.spotify_id]
                for t in liked
                if match_cache.get(t.spotify_id)
            ]
            count = ytmusic_service.like_songs(yt, liked_ids)
            state["log"].append(f"Liked {count} songs")

        # Phase 4: Transfer playlists
        if options.get("playlists") and playlists:
            for pl in playlists:
                state["phase"] = f"Creating playlist: {pl.name}"
                state["log"].append(f"Creating playlist: {pl.name}")
                vids = [
                    match_cache[t.spotify_id]
                    for t in pl.tracks
                    if match_cache.get(t.spotify_id)
                ]
                pid = ytmusic_service.create_playlist(yt, pl.name, vids)
                if pid:
                    state["log"].append(
                        f"  Created with {len(vids)}/{len(pl.tracks)} tracks"
                    )
                else:
                    state["log"].append(f"  Failed to create playlist: {pl.name}")

        # Phase 5: Transfer artists
        if options.get("artists") and artists:
            state["phase"] = "Subscribing to artists..."
            state["log"].append("Subscribing to artists...")
            sub_count = 0
            for a in artists:
                state["phase"] = f"Subscribing: {a.name}"
                if ytmusic_service.subscribe_artist(yt, a.name):
                    sub_count += 1
                state["processed"] += 1
                time.sleep(0.3)
            state["log"].append(f"Subscribed to {sub_count}/{len(artists)} artists")

        state["phase"] = "Complete!"
        state["done"] = True
        state["log"].append(
            f"Done! Matched {state['matched']}/{len(all_tracks)} tracks. "
            f"{len(state['failed_tracks'])} tracks not found."
        )

    except Exception as e:
        state["error"] = str(e)
        state["done"] = True
