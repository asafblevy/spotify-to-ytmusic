# Spotify to YouTube Music Transfer

A web app to transfer your Spotify library (liked songs, playlists, followed artists) to YouTube Music. Designed to run on your Mac and be accessed from any phone via browser.

## Setup (One Time)

### 1. Install dependencies

```bash
cd ~/spotify-to-ytmusic
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create Spotify API credentials

1. Go to https://developer.spotify.com/dashboard
2. Click **Create App**
3. Set **Redirect URI** to `http://localhost:8000/auth/spotify/callback`
   - If using ngrok: also add `https://YOUR-NGROK-URL/auth/spotify/callback`
4. Copy the **Client ID** and **Client Secret**

### 3. Create Google OAuth credentials (for YouTube Music)

1. Go to https://console.cloud.google.com/
2. Create a new project (or use existing)
3. Enable **YouTube Data API v3** in APIs & Services > Library
4. Go to **APIs & Services > OAuth consent screen**
   - Choose **External**
   - Fill in app name, email
   - Add scopes: `https://www.googleapis.com/auth/youtube`
   - Under **Test users**, add your Google email + your 2 friends' emails
5. Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Application type: **TVs and Limited Input devices**
   - Copy the **Client ID** and **Client Secret**

### 4. Configure the app

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Running

### Local (same machine)

```bash
cd ~/spotify-to-ytmusic
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

### For mobile / friends (via ngrok)

```bash
# In a separate terminal:
ngrok http 8000
```

1. Copy the ngrok HTTPS URL (e.g., `https://abc123.ngrok-free.app`)
2. Update `BASE_URL` in `.env` to the ngrok URL
3. Add the ngrok callback URL to your Spotify app's redirect URIs:
   `https://abc123.ngrok-free.app/auth/spotify/callback`
4. Restart the server
5. Share the ngrok URL with your friends — they open it in Safari/Chrome

### For mobile on same Wi-Fi (no ngrok)

```bash
# Find your local IP
ipconfig getifaddr en0

# Update BASE_URL in .env to http://YOUR_IP:8000
# Restart server, open http://YOUR_IP:8000 on phone
```

Note: Spotify requires HTTPS for redirect URIs in production. For local network,
you can add `http://YOUR_IP:8000/auth/spotify/callback` as a redirect URI in
your Spotify app dashboard (works for development/testing).

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
