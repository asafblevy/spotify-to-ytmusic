import json
import uuid
from itsdangerous import URLSafeSerializer
from fastapi import Request, Response
from app.config import settings

COOKIE_NAME = "session_id"
YT_TOKEN_COOKIE = "yt_token"
_sessions: dict[str, dict] = {}
_signer = URLSafeSerializer(settings.secret_key)


def _resolve_session(request: Request) -> tuple[str | None, dict | None]:
    """Look up session by cookie. Returns (session_id, session_dict) or (None, None)."""
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        try:
            session_id = _signer.loads(raw)
            if session_id in _sessions:
                return session_id, _sessions[session_id]
        except Exception:
            pass
    return None, None


def get_session(request: Request) -> dict | None:
    """Get existing session or None."""
    _, session = _resolve_session(request)
    return session


def ensure_session(request: Request, response: Response) -> dict:
    """Get existing session or create a new one (sets cookie on response)."""
    sid, session = _resolve_session(request)
    if session is not None:
        # Restore YTMusic token from cookie if missing from in-memory session
        # (happens after server restart / deploy)
        if "ytmusic_token" not in session:
            yt_token = _restore_yt_token(request)
            if yt_token:
                session["ytmusic_token"] = yt_token
        return session
    # Create new session
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {}
    signed = _signer.dumps(session_id)
    response.set_cookie(
        COOKIE_NAME, signed, httponly=True, samesite="lax", max_age=86400
    )
    # Restore YTMusic token from cookie if available
    yt_token = _restore_yt_token(request)
    if yt_token:
        _sessions[session_id]["ytmusic_token"] = yt_token
    return _sessions[session_id]


def save_yt_token(response: Response, token: dict) -> None:
    """Persist YTMusic token in a signed cookie so it survives server restarts."""
    signed = _signer.dumps(token)
    response.set_cookie(
        YT_TOKEN_COOKIE, signed, httponly=True, samesite="lax", max_age=86400 * 30
    )


def _restore_yt_token(request: Request) -> dict | None:
    """Restore YTMusic token from signed cookie."""
    raw = request.cookies.get(YT_TOKEN_COOKIE)
    if raw:
        try:
            return _signer.loads(raw)
        except Exception:
            pass
    return None


def clear_yt_token(response: Response) -> None:
    """Remove the persisted YTMusic token cookie."""
    response.delete_cookie(YT_TOKEN_COOKIE)
