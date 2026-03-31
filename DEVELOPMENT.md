# Development & Deployment Guide

## Architecture

- **Backend**: FastAPI (Python) with background threads for long-running transfers
- **Frontend**: Vanilla HTML/CSS/JS, mobile-first, single page
- **Auth**: Spotify OAuth2 redirect flow + Google device code flow (via ytmusicapi)
- **Sessions**: In-memory server-side dict (no database needed for small user counts)
- **Progress**: Server-Sent Events (SSE) for real-time transfer updates

## Project Structure

```
app/
├── main.py                 # FastAPI routes and SSE endpoint
├── config.py               # Pydantic settings from .env
├── session.py              # In-memory session management
├── models.py               # Pydantic models (Track, Playlist, Artist)
├── auth/
│   ├── spotify_auth.py     # Spotify OAuth2 flow
│   └── ytmusic_auth.py     # YouTube Music device code flow
├── services/
│   ├── spotify_service.py  # Fetch liked songs, playlists, artists
│   ├── ytmusic_service.py  # Like songs, create playlists, subscribe
│   ├── matcher.py          # Fuzzy song matching (Spotify → YTMusic)
│   └── transfer.py         # Transfer orchestrator with progress tracking
└── static/
    ├── index.html
    ├── style.css
    └── app.js
```

## Setup API Credentials

### Spotify

1. Go to https://developer.spotify.com/dashboard
2. Click **Create App**
3. App name: anything (e.g., "Spotify to YTMusic")
4. Redirect URI: `https://YOUR-RENDER-URL.onrender.com/auth/spotify/callback`
   (update after deploying — or use `http://localhost:8000/auth/spotify/callback` for local dev)
5. Copy the **Client ID** and **Client Secret**
6. Go to **User Management** and add email addresses for anyone who will use the app
   (required while the app is in Spotify's Development Mode)

### Google (YouTube Music)

1. Go to https://console.cloud.google.com/
2. Create a new project (or use existing)
3. Enable **YouTube Data API v3** in APIs & Services > Library
4. Go to **APIs & Services > OAuth consent screen**
   - Choose **External**
   - Fill in app name, email
   - Add scopes: `https://www.googleapis.com/auth/youtube`
   - Under **Test users**, add Google emails for everyone who will use the app
5. Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Application type: **TVs and Limited Input devices**
   - Copy the **Client ID** and **Client Secret**

## Running Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials (set BASE_URL=http://localhost:8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Deploy to Render

1. Go to https://render.com and sign in with GitHub
2. Click **New > Web Service** and select this repo
3. It auto-detects the Dockerfile — click **Create Web Service**
4. Once deployed, copy your URL (e.g., `https://spotify-to-ytmusic-xxxx.onrender.com`)
5. In Render dashboard → your service → **Environment**, add:

| Key | Value |
|-----|-------|
| `SPOTIFY_CLIENT_ID` | from Spotify dashboard |
| `SPOTIFY_CLIENT_SECRET` | from Spotify dashboard |
| `GOOGLE_CLIENT_ID` | from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | from Google Cloud Console |
| `BASE_URL` | your full Render URL |
| `SECRET_KEY` | any random string |

6. Update Spotify redirect URI to: `https://YOUR-RENDER-URL.onrender.com/auth/spotify/callback`

## Debug Endpoint

Hit `/debug/session` in the browser to inspect the current session state (auth tokens present, transfer state, etc.).

## Key Technical Notes

- **Song matching** uses fuzzy string matching (thefuzz) with multiple search strategies: artist+title, title+artist, title-only. Duration comparison is used as a tiebreaker.
- **Rate limiting**: 0.4s delay between YouTube Music searches, 0.3s between like/subscribe operations. Large libraries (1000+ songs) take ~10 minutes.
- **Spotify token refresh**: tokens expire after 1 hour. The transfer re-authenticates before each phase to handle long-running transfers.
- **Inaccessible playlists**: Spotify-generated playlists (Discover Weekly, etc.) return 403 and are skipped automatically.
- **In-memory sessions**: sessions live in a Python dict — a server restart clears all sessions. Fine for small-scale use.
