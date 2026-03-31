# Spotify to YouTube Music Transfer

A mobile-friendly web app to transfer your Spotify library (liked songs, playlists, followed artists) to YouTube Music. Hosted on Render — just share the link with friends.

## Deployment on Render (Recommended)

### 1. Create Spotify API credentials

1. Go to https://developer.spotify.com/dashboard
2. Click **Create App**
3. App name: anything (e.g., "Spotify to YTMusic")
4. Redirect URI: `https://YOUR-RENDER-URL.onrender.com/auth/spotify/callback`
   (you'll get this URL after deploying — come back and update it)
5. Copy the **Client ID** and **Client Secret**
6. Go to **User Management** and add your friends' Spotify email addresses
   (required while the app is in Development Mode)

### 2. Create Google OAuth credentials (for YouTube Music)

1. Go to https://console.cloud.google.com/
2. Create a new project (or use existing)
3. Enable **YouTube Data API v3** in APIs & Services > Library
4. Go to **APIs & Services > OAuth consent screen**
   - Choose **External**
   - Fill in app name, email
   - Add scopes: `https://www.googleapis.com/auth/youtube`
   - Under **Test users**, add your Google email + your friends' emails
5. Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Application type: **TVs and Limited Input devices**
   - Copy the **Client ID** and **Client Secret**

### 3. Deploy to Render

1. Go to https://render.com and sign in with GitHub
2. Click **New > Web Service** and select this repo
3. It auto-detects the Dockerfile — click **Create Web Service**
4. Once deployed, copy your URL (e.g., `https://spotify-to-ytmusic-xxxx.onrender.com`)

### 4. Set environment variables

In Render dashboard → your service → **Environment**, add:

| Key | Value |
|-----|-------|
| `SPOTIFY_CLIENT_ID` | from step 1 |
| `SPOTIFY_CLIENT_SECRET` | from step 1 |
| `GOOGLE_CLIENT_ID` | from step 2 |
| `GOOGLE_CLIENT_SECRET` | from step 2 |
| `BASE_URL` | your full Render URL (e.g., `https://spotify-to-ytmusic-xxxx.onrender.com`) |
| `SECRET_KEY` | any random string |

### 5. Update Spotify redirect URI

Go back to your Spotify app dashboard and set the redirect URI to:
`https://YOUR-RENDER-URL.onrender.com/auth/spotify/callback`

### 6. Share the link

Send your Render URL to friends. They open it on their phone, connect both accounts, and transfer.

## Running Locally (Optional)

```bash
cd ~/spotify-to-ytmusic
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials (set BASE_URL=http://localhost:8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Add `http://localhost:8000/auth/spotify/callback` as a redirect URI in your Spotify app.

## How It Works

1. **Connect Spotify** — Standard OAuth login in browser
2. **Connect YouTube Music** — Google device code flow: you'll see a code, tap the link, enter the code on Google's site, and grant access
3. **Preview** — Shows your library stats (liked songs, playlists, artists)
4. **Transfer** — Searches YouTube Music for each track by artist + title, uses fuzzy matching. Creates playlists, likes songs, subscribes to artists
5. **Report** — Shows what matched and what wasn't found

## Expected Performance

- ~1000 liked songs takes ~7-10 minutes (rate-limited to avoid YouTube API throttling)
- Match rate: typically 85-95% depending on your library
- Songs not found are listed in the final report

## Troubleshooting

- **"Not authenticated"** — Tokens expired. Click Disconnect & Start Over, reconnect both services
- **YouTube Music auth fails** — Make sure your Google email is listed as a test user in the OAuth consent screen
- **Low match rate** — Some songs are region-locked or not available on YouTube Music
