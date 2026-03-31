import traceback
import time
from app.models import Track, MatchResult
from app.services import matcher, ytmusic_service
from app.auth.spotify_auth import get_spotify_client
from app.services.spotify_service import (
    fetch_liked_songs,
    fetch_playlists,
    fetch_followed_artists,
)


def run_transfer(session: dict, options: dict) -> None:
    """Run the full transfer. Updates session['transfer_state'] as it goes."""
    state = session["transfer_state"]
    state.update(
        {
            "phase": "Initializing...",
            "total": 0,
            "processed": 0,
            "matched": 0,
            "failed_tracks": [],
            "done": False,
            "error": None,
            "log": ["Transfer started..."],
        }
    )

    try:
        state["log"].append("Authenticating with Spotify...")
        sp = get_spotify_client(session)
        if not sp:
            state["error"] = "Spotify authentication failed. Please reconnect."
            state["done"] = True
            return

        state["log"].append("Checking YouTube Music credentials...")
        if "ytmusic_token" not in session or "access_token" not in session.get("ytmusic_token", {}):
            state["error"] = "YouTube Music authentication failed. Please reconnect."
            state["done"] = True
            return

        state["log"].append("Both services connected!")

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
            sp = get_spotify_client(session)

            def playlist_progress(msg):
                state["phase"] = msg

            playlists, skipped = fetch_playlists(sp, on_progress=playlist_progress)
            state["log"].append(
                f"Found {len(playlists)} playlists "
                f"({sum(len(p.tracks) for p in playlists)} total tracks)"
            )
            if skipped:
                state["log"].append(
                    f"Skipped {len(skipped)} inaccessible playlists: {', '.join(skipped)}"
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

        # Phase 2: Match tracks (uses yt-dlp, no auth needed)
        state["phase"] = "Matching songs on YouTube..."
        match_cache: dict[str, str | None] = {}

        for i, (sid, track) in enumerate(all_tracks.items()):
            state["phase"] = f"Matching ({i+1}/{len(all_tracks)}): {track.artist} - {track.title}"

            debug_log = [] if i < 5 else None
            video_id, score = matcher.find_match(None, track, debug_log=debug_log)
            match_cache[sid] = video_id
            state["processed"] += 1

            if video_id:
                state["matched"] += 1
            else:
                state["failed_tracks"].append(
                    f"{track.artist} - {track.title} (score: {score:.0f})"
                )

            if debug_log:
                for line in debug_log:
                    state["log"].append(line)
                state["log"].append(
                    f"  => {track.artist} - {track.title}: "
                    f"{'MATCHED' if video_id else 'FAILED'} (score={score:.0f})"
                )

            time.sleep(0.2)

        # Phase 3: Transfer liked songs → YouTube Liked Music
        if options.get("liked_songs") and liked:
            state["phase"] = "Adding songs to YouTube Liked Music..."
            state["log"].append("Adding matched songs to your YouTube Liked Music...")
            seen = set()
            liked_ids = []
            for t in liked:
                vid = match_cache.get(t.spotify_id)
                if vid and vid not in seen:
                    seen.add(vid)
                    liked_ids.append(vid)
            count = ytmusic_service.like_songs(session, liked_ids)
            state["log"].append(f"Added {count} songs to Liked Music")

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
                pid = ytmusic_service.create_playlist(session, pl.name, vids)
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
                if ytmusic_service.subscribe_artist(session, a.name):
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
        state["error"] = f"{type(e).__name__}: {e}"
        state["log"].append(f"ERROR: {type(e).__name__}: {e}")
        state["log"].append(traceback.format_exc())
        state["done"] = True
