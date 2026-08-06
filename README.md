# knicks-auto-daily

Fully automated daily YouTube videos for **NY Knicks Daily**.

## How it works (all inside GitHub Actions)

Every day at 12:00 UTC (15:00 Istanbul) the `daily-video` workflow:

1. **generate.py** — Claude (Anthropic API + web search) researches today's Knicks
   news and writes a ~30-minute narration script (`content/current/script.json`)
   plus YouTube metadata (`meta.json`). Topic history in `content/topics_log.txt`
   prevents repeats.
2. **tts.py** — ElevenLabs (voice: Alex Smooth, model: Flash v2.5) narrates it.
   Falls back to Piper (offline) if no ElevenLabs key is set.
3. **visuals.py** — generates branded 1080p info cards + thumbnail (Knicks palette).
4. **assemble.py** — ffmpeg renders cards with slow zoom, synced to narration.
5. **upload.py** — uploads to YouTube (title, description, tags, thumbnail,
   AI-content disclosure). Result appears in the run's Summary.

`render-upload` workflow: re-renders on manual edits to `content/current/`.
`oauth-exchange` workflow: one-time YouTube authorization helper.

## Required repository secrets (Settings → Secrets and variables → Actions)

| Secret | What |
|---|---|
| `YT_CLIENT_ID` | Google OAuth client id |
| `YT_CLIENT_SECRET` | Google OAuth client secret |
| `YT_REFRESH_TOKEN` | set automatically by the oauth-exchange workflow |
| `ADMIN_PAT` | GitHub personal access token (repo+workflow) |
| `ELEVEN_API_KEY` | ElevenLabs API key |
| `ANTHROPIC_API_KEY` | Anthropic API key (script generation) |

Optional variables (Settings → ... → Variables): `ELEVEN_VOICE` (default "alex"),
`ELEVEN_MODEL` (default eleven_flash_v2_5), `MODEL` (default claude-sonnet-4-5),
`TARGET_MINUTES` (default 30).

## Manual run

Actions → daily-video → Run workflow (choose privacy: private for a test).
