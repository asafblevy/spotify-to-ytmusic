# Spotify to YouTube Music Transfer

Transfer your Spotify library (liked songs, playlists, followed artists) to YouTube Music. Works on mobile — just open the link in your browser.

## How to Use

1. Open the app link shared with you
2. **Connect Spotify** — tap the button, log in with your Spotify account
3. **Connect YouTube Music** — tap the button, you'll see a code. Tap the link to go to Google, enter the code, and grant access
4. **Choose what to transfer** — liked songs, playlists, artists (or all three)
5. **Start Transfer** — sit back and watch the progress. The app searches YouTube Music for each song and adds matches to your library
6. **Review** — see what matched and what wasn't found

## What to Expect

- ~1000 songs takes ~7-10 minutes (rate-limited to be safe with YouTube's API)
- Typical match rate: 85-95% depending on your library
- Some songs won't be found due to regional licensing or not being on YouTube Music
- Spotify-generated playlists (Discover Weekly, Daily Mix, etc.) may be skipped

## Troubleshooting

- **"Not authenticated"** — tokens expired. Tap Disconnect & Start Over, reconnect both services
- **YouTube Music auth fails** — ask the app owner to add your Google email as a test user
- **Transfer seems stuck** — it's probably just working through a large library. The progress bar and log update in real time
