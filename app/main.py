import asyncio
import json
import threading

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.session import get_session, ensure_session, save_yt_token, clear_yt_token
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
        save_yt_token(response, token)
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
    session["transfer_state"] = {}
    thread = threading.Thread(target=run_transfer, args=(session, options), daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/transfer/progress")
async def transfer_progress(request: Request):
    session = get_session(request)
    if not session:
        async def error_gen():
            yield {"event": "progress", "data": json.dumps({"done": True, "error": "No session found. Please refresh and try again."})}
        return EventSourceResponse(error_gen())

    async def event_generator():
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


# --- Dedup (client-side, just serves the page) ---
@app.get("/dedup", response_class=HTMLResponse)
async def dedup_page():
    with open("app/static/dedup.html") as f:
        return f.read()


# --- Bulk Like (client-side, just serves the page) ---
@app.get("/bulk-like", response_class=HTMLResponse)
async def bulk_like_page():
    with open("app/static/bulk-like.html") as f:
        return f.read()


# --- Logout ---
@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    session = ensure_session(request, response)
    session.clear()
    response.delete_cookie("session_id")
    clear_yt_token(response)
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
async def debug_search(q: str = "PinkPantheress Stateside"):
    """Test yt-dlp search. No auth needed."""
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            results = ydl.extract_info(f"ytsearch3:{q}", download=False)
        return {
            "query": q,
            "results": [
                {
                    "videoId": e.get("id"),
                    "title": e.get("title"),
                    "channel": e.get("channel") or e.get("uploader"),
                    "duration": e.get("duration"),
                }
                for e in results.get("entries", [])[:3]
            ],
        }
    except Exception as e:
        import traceback
        return {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}


# --- Static files & index ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("app/static/index.html") as f:
        return f.read()
