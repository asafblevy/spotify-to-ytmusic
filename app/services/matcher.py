import re
import yt_dlp
from thefuzz import fuzz
from app.models import Track

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "default_search": "ytsearch5",
}


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", s)
    s = re.sub(r"\s*-\s*(official\s*)?(music\s*)?(video|audio|lyric|visualizer).*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _score_result(title: str, channel: str, duration_sec: float, track: Track) -> float:
    norm_title = _normalize(title)

    title_score = fuzz.ratio(norm_title, _normalize(track.title))
    # Also try matching against "artist - title" since YT titles often use that format
    full_ref = f"{_normalize(track.artist)} {_normalize(track.title)}"
    full_score = fuzz.ratio(norm_title, full_ref)
    title_score = max(title_score, full_score)

    artist_score = 0
    norm_channel = _normalize(channel)
    for sp_artist in track.all_artists:
        norm_artist = _normalize(sp_artist)
        score = fuzz.ratio(norm_artist, norm_channel)
        artist_score = max(artist_score, score)
        if norm_artist in norm_channel:
            artist_score = max(artist_score, 90)
        if norm_artist in norm_title:
            artist_score = max(artist_score, 85)

    duration_bonus = 0
    if duration_sec and track.duration_ms:
        diff = abs(duration_sec - track.duration_ms / 1000)
        if diff < 3:
            duration_bonus = 10
        elif diff < 10:
            duration_bonus = 5
        elif diff > 30:
            duration_bonus = -10

    combined = (title_score * 0.45) + (artist_score * 0.45) + duration_bonus
    return min(100, max(0, combined))


def find_match(yt, track: Track, debug_log=None) -> tuple[str | None, float]:
    """Find the best YouTube match using yt-dlp search.
    Returns (videoId, score) or (None, 0)."""

    query = f"ytsearch5:{track.artist} - {track.title}"

    try:
        with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
            results = ydl.extract_info(query, download=False)

        best_id = None
        best_score = 0.0

        for entry in results.get("entries", []):
            vid = entry.get("id")
            title = entry.get("title", "")
            channel = entry.get("channel") or entry.get("uploader", "")
            duration = entry.get("duration") or 0

            score = _score_result(title, channel, duration, track)

            if debug_log is not None:
                debug_log.append(f"  [{score:.0f}] {channel} - {title} ({duration}s)")

            if score > best_score:
                best_score = score
                best_id = vid

        if best_score >= 40:
            return best_id, best_score

        if debug_log is not None:
            debug_log.append("  No good match found")

        return None, best_score

    except Exception as e:
        if debug_log is not None:
            debug_log.append(f"  Search error: {type(e).__name__}: {e}")
        return None, 0.0
