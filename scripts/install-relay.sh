#!/bin/sh
# Install (or reinstall) a macOS LaunchAgent that runs `veille relay` every 4 hours.
# It fetches the feeds marked `local: true` in config.yaml (Substack blocks GitHub's servers)
# and pushes relay/local_items.json so the GitHub Action can include them.
#
#   sh scripts/install-relay.sh            install / update
#   sh scripts/install-relay.sh uninstall  remove
set -eu

LABEL="com.tap-veille.relay"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$HOME/Library/Logs/tap-veille-relay.log"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ "${1:-}" = "uninstall" ]; then
  rm -f "$PLIST"
  echo "Removed $LABEL"
  exit 0
fi

[ -x "$ROOT/.venv/bin/veille" ] || { echo "Run first: python3 -m venv .venv && .venv/bin/pip install -e ."; exit 1; }

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$ROOT/.venv/bin/veille</string><string>relay</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartInterval</key><integer>14400</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $LABEL: runs now and every 4 hours (while the Mac is awake). Log: $LOG"
