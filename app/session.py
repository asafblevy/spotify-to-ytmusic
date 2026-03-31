import uuid
from itsdangerous import URLSafeSerializer
from fastapi import Request, Response
from app.config import settings

COOKIE_NAME = "session_id"
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
        return session
    # Create new session
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {}
    signed = _signer.dumps(session_id)
    response.set_cookie(
        COOKIE_NAME, signed, httponly=True, samesite="lax", max_age=86400
    )
    return _sessions[session_id]
