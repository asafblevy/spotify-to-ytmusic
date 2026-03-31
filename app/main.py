import asyncio
import json
import threading

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.session import get_session, ensure_session
from app.auth.spotify_auth import get_spotify_oauth, get_spotify_client
from app.auth.ytmusic_auth import start_device_flow, poll_device_flow, get_ytmusic_client
from app.services.spotify_service import fetch_liked_songs, fetch_playlists, fetch_followed_artists
from app.services.transfer import run_transfer

app = FastAPI(title="Spotify to YouTube Music Transfer")


# --- Auth Status ---
@app.get("/auth/status")
async def auth_status(request: Request, response: Response):
    session = ensure_session(request, response)
    return {
        "spotify": "spotify_token" in session,
        "ytmusic": "ytmusic_token" in session,
    }


# --- Spotify OAuth ---
@app.get("/auth/spotify/login")
async def spotify_login(request: Request, response: Response):
    session = ensure_session(request, response)
    oauth = get_spotify_oauth(session)
    auth_url = oauth.get_authorize_url()
    return RedirectResponse(auth_url)


@app.get("/auth/spotify/callback")
async def spotify_callback(request: Request, response: Response, code: str = ""):
    session = ensure_session(request, response)
    if not code:
        return RedirectResponse("/")
    oauth = get_spotify_oauth(session)
    token_info = oauth.get_access_token(code, as_dict=True)
    session["spotify_token"] = token_info
    return RedirectResponse("/")


# --- YouTube Music Device Code Flow ---
@app.post("/auth/ytmusic/start")
async def ytmusic_start(request: Request, response: Response):
    session = ensure_session(request, response)
    code_info = start_device_flow()
    session["ytmusic_device_code"] = code_info.get("device_code")
    return {
        "user_code": code_info.get("user_code"),
        "verification_url": code_info.get("verification_url"),
    }


@app.get("/auth/ytmusic/poll")
async def ytmusic_poll(request: Request, response: Response):
    session = ensure_session(request, response)
    device_code = session.get("ytmusic_device_code")
    if not device_code:
        return {"status": "error", "message": "No device code flow started"}
    token = poll_device_flow(device_code)
    if token:
        session["ytmusic_token"] = token
        return {"status": "complete"}
    return {"status": "pending"}


# --- Library Preview ---
@app.get("/library/preview")
async def library_preview(request: Request, response: Response):
    session = ensure_session(request, response)
    sp = get_spotify_client(session)
    if not sp:
        return JSONResponse({"error": "Spotify not connected"}, status_code=401)

    try:
        # Quick counts — just fetch first page to get totals
        liked = sp.current_user_saved_tracks(limit=1)
        liked_total = liked.get("total", 0) if liked else 0

        playlists = sp.current_user_playlists(limit=1)
        playlists_total = playlists.get("total", 0) if playlists else 0

        artists = sp.current_user_followed_artists(limit=1)
        artists_total = artists.get("artists", {}).get("total", 0) if artists else 0

        return {
            "liked_songs": liked_total,
            "playlists": playlists_total,
            "artists": artists_total,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# --- Transfer ---
@app.post("/transfer/start")
async def transfer_start(request: Request, response: Response):
    session = ensure_session(request, response)
    body = await request.json()
    options = {
        "liked_songs": body.get("liked_songs", True),
        "playlists": body.get("playlists", True),
        "artists": body.get("artists", True),
    }
    # Run transfer in a background thread (it's synchronous/blocking)
    session["transfer_state"] = {}
    thread = threading.Thread(target=run_transfer, args=(session, options), daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/transfer/progress")
async def transfer_progress(request: Request):
    # Use get_session directly (read-only, no new cookie needed for SSE)
    session = get_session(request)
    if not session:
        async def error_gen():
            yield {"event": "progress", "data": json.dumps({"done": True, "error": "No session found. Please refresh and try again."})}
        return EventSourceResponse(error_gen())

    async def event_generator():
        # Wait briefly for transfer thread to initialize state
        for _ in range(10):
            state = session.get("transfer_state")
            if state and state.get("phase"):
                break
            await asyncio.sleep(0.5)

        while True:
            state = session.get("transfer_state", {})
            yield {"event": "progress", "data": json.dumps(state)}
            if state.get("done"):
                break
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


# --- Logout ---
@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    session = ensure_session(request, response)
    session.clear()
    response.delete_cookie("session_id")
    return {"status": "ok"}


# --- Debug ---
@app.get("/debug/session")
async def debug_session(request: Request, response: Response):
    session = ensure_session(request, response)
    return {
        "has_spotify_token": "spotify_token" in session,
        "has_ytmusic_token": "ytmusic_token" in session,
        "transfer_state": session.get("transfer_state"),
        "session_keys": list(session.keys()),
    }


@app.get("/debug/search")
async def debug_search(request: Request, response: Response, q: str = "PinkPantheress Stateside"):
    """Test YouTube Music search directly. Usage: /debug/search?q=artist+title"""
    session = ensure_session(request, response)
    yt = get_ytmusic_client(session)
    if not yt:
        return {"error": "YouTube Music not connected"}
    try:
        results_songs = yt.search(q, filter="songs", limit=3)
        results_any = yt.search(q, limit=3)
        return {
            "query": q,
            "songs_filter": [
                {
                    "title": r.get("title"),
                    "artists": [a.get("name") for a in r.get("artists", [])],
                    "videoId": r.get("videoId"),
                    "resultType": r.get("resultType"),
                    "duration": r.get("duration"),
                    "duration_seconds": r.get("duration_seconds"),
                }
                for r in (results_songs or [])[:3]
            ],
            "no_filter": [
                {
                    "title": r.get("title"),
                    "artists": [a.get("name") for a in r.get("artists", [])],
                    "videoId": r.get("videoId"),
                    "resultType": r.get("resultType"),
                    "category": r.get("category"),
                }
                for r in (results_any or [])[:5]
            ],
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# --- Static files & index ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("app/static/index.html") as f:
        return f.read()
