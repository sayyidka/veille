# TàP veille

A personal feed for YouTube research on **tech & AI in daily life**, **attention / reading / writing**, and **AI skepticism**.
It pulls Hacker News, Lemmy (open Reddit alternative), Bluesky (shared articles only), Tildes, Lobsters, Google News (EN + FR),
curated RSS (newsletters, essays, podcasts), studies (OpenAlex + arXiv), and Reddit when API keys are set. It keeps what matches the
keywords in `config.yaml`, and builds one mobile-friendly static page: `site/index.html`.

## Run locally
```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/veille run            # fetch + build
.venv/bin/veille serve          # → http://localhost:8000
```
To try it on your phone before deploying: `.venv/bin/veille serve --lan`, then open the printed
`http://192.168.x.x:8000` address on your phone (same Wi-Fi). Ctrl+C stops the server.
Other commands: `veille fetch`, `veille build` (re-score existing data after editing keywords, no network),
`veille fetch --only hn rss`.

## Tune it
Everything lives in `config.yaml`:
- `topics.*.keywords`: weighted keywords (accent-insensitive, whole words). An item is kept when one topic reaches `settings.threshold`.
- `exclude` / `exclude_sources`: drop noise (finance, promos…).
- `sources`: add subreddits, RSS feeds, HN / Google News / OpenAlex queries. `min_score: 0` on a source keeps all of its posts;
  `skeptic: true` puts them in the "AI skepticism" tab.

After editing keywords, run `veille build` to see the effect immediately.

## Deploy (to read it on your phone)
1. Push this folder to a GitHub repo (e.g. `veille`).
2. Repo **Settings → Pages → Source: GitHub Actions**.
3. **Reddit keys** (optional: Reddit is skipped without them, as it blocks anonymous calls):
   - Go to https://www.reddit.com/prefs/apps → "create another app…" → type **script**, any name, redirect URI `http://localhost`.
   - Copy the client id (under the app name) and the secret.
   - Repo **Settings → Secrets and variables → Actions**: add `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`.
   - Locally: `export REDDIT_CLIENT_ID=… REDDIT_CLIENT_SECRET=…` before `veille run`.
4. **Actions → Update feed → Run workflow**. It then runs every 6 hours on its own.
5. Open `https://<your-user>.github.io/veille/` on your phone → Share → **Add to Home Screen**.

Note: GitHub Pages sites are public. The page only contains public links, but if you want it private, Cloudflare Pages + Access
(free) is the easiest alternative.
