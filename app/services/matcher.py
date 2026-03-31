import re
from thefuzz import fuzz
from ytmusicapi import YTMusic
from app.models import Track
from app.auth.ytmusic_auth import get_search_client


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
    yt_duration = result.get("duration_seconds") or result.get("duration", 0) or 0

    # If duration is a string like "3:45", convert to seconds
    if isinstance(yt_duration, str) and ":" in yt_duration:
        parts = yt_duration.split(":")
        try:
            yt_duration = int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            yt_duration = 0

    title_score = fuzz.ratio(_normalize(yt_title), _normalize(track.title))

    artist_score = 0
    for sp_artist in track.all_artists:
        for yt_artist in yt_artists:
            score = fuzz.ratio(_normalize(sp_artist), _normalize(yt_artist))
            artist_score = max(artist_score, score)

    duration_bonus = 0
    if yt_duration and track.duration_ms:
        diff = abs(yt_duration - track.duration_ms / 1000)
        if diff < 3:
            duration_bonus = 10
        elif diff < 10:
            duration_bonus = 5
        elif diff > 30:
            duration_bonus = -10

    combined = (title_score * 0.55) + (artist_score * 0.45) + duration_bonus
    return min(100, max(0, combined))


def find_match(yt: YTMusic, track: Track, debug_log=None) -> tuple[str | None, float]:
    """Find the best YTMusic match for a Spotify track.
    Uses unauthenticated client for search (OAuth client gets 400 errors).
    Returns (videoId, score) or (None, 0).
    debug_log: optional list to append debug info to."""

    search_client = get_search_client()

    strategies = [
        (f"{track.artist} {track.title}", "songs"),
        (f"{track.title} {track.artist}", None),
        (track.title, "songs"),
    ]

    best_id = None
    best_score = 0.0
    total_results = 0

    for query, filt in strategies:
        try:
            kwargs = {"query": query, "limit": 10}
            if filt:
                kwargs["filter"] = filt
            results = search_client.search(**kwargs)

            if not results:
                if debug_log is not None:
                    debug_log.append(f"  Search '{query}' (filter={filt}): no results")
                continue

            for r in results:
                rt = r.get("resultType")
                vid = r.get("videoId")
                if not vid:
                    continue
                # Accept songs, videos, and anything with a videoId
                if rt and rt not in ("song", "video"):
                    continue
                total_results += 1
                score = _score_result(r, track)
                if score > best_score:
                    best_score = score
                    best_id = vid

                    if debug_log is not None and total_results <= 3:
                        yt_title = r.get("title", "?")
                        yt_artist = ", ".join(a.get("name", "") for a in r.get("artists", []))
                        debug_log.append(
                            f"  Candidate: {yt_artist} - {yt_title} "
                            f"(score={score:.0f}, type={rt})"
                        )

            if best_score >= 80:
                return best_id, best_score
        except Exception as e:
            if debug_log is not None:
                debug_log.append(f"  Search error: {type(e).__name__}: {e}")
            continue

    # Lower threshold — accept anything reasonable
    if best_score >= 45:
        return best_id, best_score

    if debug_log is not None and total_results == 0:
        debug_log.append(f"  No results found across all strategies")

    return None, best_score
