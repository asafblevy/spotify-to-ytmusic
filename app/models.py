from pydantic import BaseModel


class Track(BaseModel):
    spotify_id: str
    title: str
    artist: str
    all_artists: list[str]
    album: str
    duration_ms: int


class Playlist(BaseModel):
    spotify_id: str
    name: str
    tracks: list[Track]


class Artist(BaseModel):
    spotify_id: str
    name: str


class MatchResult(BaseModel):
    track: Track
    ytmusic_video_id: str | None = None
    match_score: float = 0.0
    status: str = "pending"  # matched, not_found, error
