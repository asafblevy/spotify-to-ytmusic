import uuid
from itsdangerous import URLSafeSerializer
from fastapi import Request, Response
from app.config import settings

COOKIE_NAME = "session_id"
_sessions: dict[str, dict] = {}
_signer = URLSafeSerializer(settings.secret_key)


def get_session(request: Request) -> dict:
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        try:
            session_id = _signer.loads(raw)
            if session_id in _sessions:
                return _sessions[session_id]
        except Exception:
            pass
    return {}


def create_session(response: Response) -> dict:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {}
    signed = _signer.dumps(session_id)
    response.set_cookie(
        COOKIE_NAME, signed, httponly=True, samesite="lax", max_age=86400
    )
    return _sessions[session_id]


def ensure_session(request: Request, response: Response) -> dict:
    session = get_session(request)
    if not session and session is not None:
        # empty dict from no cookie — create new
        raw = request.cookies.get(COOKIE_NAME)
        if raw:
            try:
                session_id = _signer.loads(raw)
                if session_id in _sessions:
                    return _sessions[session_id]
            except Exception:
                pass
        session = create_session(response)
    return session
