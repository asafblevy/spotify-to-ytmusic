import re
from thefuzz import fuzz
from ytmusicapi import YTMusic
from app.models import Track

# Minimum fuzz ratio to accept a match
TITLE_THRESHOLD = 75
ARTIST_THRESHOLD = 70


def _normalize(s: str) -> str:
    """Lowercase, strip parenthetical info like (feat. ...), (Remastered), etc."""
    s = s.lower().strip()
    s = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _score_result(result: dict, track: Track) -> float:
    """Score a YTMusic search result against a Spotify track. Returns 0-100."""
    yt_title = result.get("title", "")
    yt_artists = [a.get("name", "") for a in result.get("artists", [])]
    yt_duration = result.get("duration_seconds", 0) or 0

    # Title similarity
    title_score = fuzz.ratio(_normalize(yt_title), _normalize(track.title))

    # Artist similarity — check best match across all artist combinations
    artist_score = 0
    for sp_artist in track.all_artists:
        for yt_artist in yt_artists:
            score = fuzz.ratio(_normalize(sp_artist), _normalize(yt_artist))
            artist_score = max(artist_score, score)

    # Duration similarity (bonus/penalty)
    duration_bonus = 0
    if yt_duration and track.duration_ms:
        diff = abs(yt_duration - track.duration_ms / 1000)
        if diff < 3:
            duration_bonus = 10
        elif diff < 10:
            duration_bonus = 5
        elif diff > 30:
            duration_bonus = -15

    combined = (title_score * 0.55) + (artist_score * 0.45) + duration_bonus
    return min(100, max(0, combined))


def find_match(yt: YTMusic, track: Track) -> tuple[str | None, float]:
    """Find the best YTMusic match for a Spotify track.
    Returns (videoId, score) or (None, 0)."""

    strategies = [
        # Strategy 1: artist - title, songs filter
        (f"{track.artist} {track.title}", "songs"),
        # Strategy 2: title + artist, no filter
        (f"{track.title} {track.artist}", None),
        # Strategy 3: title only
        (track.title, "songs"),
    ]

    best_id = None
    best_score = 0.0

    for query, filt in strategies:
        try:
            kwargs = {"query": query, "limit": 5}
            if filt:
                kwargs["filter"] = filt
            results = yt.search(**kwargs)

            for r in results:
                if r.get("resultType") not in ("song", "video", None):
                    continue
                vid = r.get("videoId")
                if not vid:
                    continue
                score = _score_result(r, track)
                if score > best_score:
                    best_score = score
                    best_id = vid

            if best_score >= 85:
                return best_id, best_score
        except Exception:
            continue

    if best_score >= 60:
        return best_id, best_score
    return None, best_score
