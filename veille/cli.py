import argparse
import http.server
import logging
import socket
import time
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

import yaml

from . import db
from .build import ROOT, build
from .fetchers import arxiv, bluesky, google_news, hn, lemmy, make_client, openalex, reddit, rss

log = logging.getLogger("veille")

FETCHERS = {
    "hn": hn.fetch,
    "reddit": reddit.fetch,
    "lemmy": lemmy.fetch,
    "bluesky": bluesky.fetch,
    "google_news": google_news.fetch,
    "rss": rss.fetch,
    "openalex": openalex.fetch,
    "arxiv": arxiv.fetch,
}


def load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_fetch(conn, config: dict, only: list[str] | None) -> None:
    with make_client(config) as client:
        for name, fn in FETCHERS.items():
            if only and name not in only:
                continue
            if name not in config["sources"]:
                continue
            t0 = time.time()
            try:
                items = fn(config, client)
            except Exception:  # one broken source must not break the run
                log.exception("Source %s crashed", name)
                continue
            # Skip entries far outside the window (e.g. a podcast's full back catalogue)
            cutoff = datetime.now(timezone.utc) - timedelta(days=2 * config["settings"]["window_days"])
            items = [i for i in items if i.published >= cutoff]
            new = db.upsert(conn, items)
            log.info("%-12s %4d fetched, %4d new  (%.1fs)", name, len(items), new, time.time() - t0)
    db.prune(conn, config["settings"]["window_days"])


def _lan_ip() -> str | None:
    """Best-effort local network IP (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def cmd_serve(port: int, lan: bool) -> None:
    site = ROOT / "site"
    if not (site / "index.html").exists():
        raise SystemExit("site/index.html not found: run `veille run` (or `veille build`) first.")
    host = "0.0.0.0" if lan else "127.0.0.1"
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    with http.server.ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"\n  Veille is served at  http://localhost:{port}/")
        if lan:
            ip = _lan_ip()
            print(f"  On your phone (same Wi-Fi):  http://{ip or '<your-mac-ip>'}:{port}/")
        else:
            print("  (add --lan to open it from your phone on the same Wi-Fi)")
        print("  Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(prog="veille", description="Topic aggregator")
    parser.add_argument("command", choices=["fetch", "build", "run", "serve"],
                        help="run = fetch + build; serve = preview site/ in a browser")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "veille.db")
    parser.add_argument("--only", nargs="*", choices=list(FETCHERS), help="fetch only these sources")
    parser.add_argument("--port", type=int, default=8000, help="serve: port (default 8000)")
    parser.add_argument("--lan", action="store_true", help="serve: also reachable from other devices on your Wi-Fi")
    args = parser.parse_args()

    if args.command == "serve":
        return cmd_serve(args.port, args.lan)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config(args.config)
    conn = db.connect(args.db)
    if args.command in ("fetch", "run"):
        cmd_fetch(conn, config, args.only)
    if args.command in ("build", "run"):
        build(conn, config)


if __name__ == "__main__":
    main()
