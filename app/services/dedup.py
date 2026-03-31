import time
from ytmusicapi import YTMusic


def run_dedup(session: dict) -> None:
    """Go over all YTMusic playlists and remove duplicate tracks. Updates session['dedup_state']."""
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
        from app.auth.ytmusic_auth import get_ytmusic_client
        yt = get_ytmusic_client(session)
        if not yt:
            state["error"] = "YouTube Music not connected"
            state["done"] = True
            return

        # Fetch all playlists
        state["phase"] = "Fetching your YouTube Music playlists..."
        state["log"].append("Fetching playlists...")
        playlists = yt.get_library_playlists(limit=100)
        state["total_playlists"] = len(playlists)
        state["log"].append(f"Found {len(playlists)} playlists")

        for i, pl in enumerate(playlists):
            pl_id = pl.get("playlistId")
            pl_title = pl.get("title", "Unknown")
            state["phase"] = f"Checking ({i+1}/{len(playlists)}): {pl_title}"
            state["processed_playlists"] = i + 1

            if not pl_id:
                continue

            try:
                # Fetch full playlist with all tracks
                full_pl = yt.get_playlist(pl_id, limit=5000)
                tracks = full_pl.get("tracks", [])

                if not tracks:
                    continue

                # Find duplicates by videoId
                seen = set()
                dupes_to_remove = []
                for track in tracks:
                    vid = track.get("videoId")
                    if not vid:
                        continue
                    if vid in seen:
                        # This is a duplicate — collect its setVideoId for removal
                        set_video_id = track.get("setVideoId")
                        if set_video_id:
                            dupes_to_remove.append({
                                "videoId": vid,
                                "setVideoId": set_video_id,
                            })
                    else:
                        seen.add(vid)

                if dupes_to_remove:
                    state["log"].append(
                        f"{pl_title}: removing {len(dupes_to_remove)} duplicates "
                        f"(keeping {len(seen)}/{len(tracks)})"
                    )
                    try:
                        yt.remove_playlist_items(pl_id, dupes_to_remove)
                        state["total_removed"] += len(dupes_to_remove)
                    except Exception as e:
                        state["log"].append(f"  Error removing from {pl_title}: {e}")
                    time.sleep(0.5)

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
