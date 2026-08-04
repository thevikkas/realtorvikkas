#!/bin/bash
# Realtor Vikkas — double-click launcher for macOS.
# Double-click this file in Finder to start the website and open it in your browser.

cd "$(dirname "$0")" || exit 1
PORT="${PORT:-8000}"

echo "──────────────────────────────────────────────"
echo "  Realtor Vikkas"
echo "  Starting the website on http://localhost:$PORT"
echo "  Keep this window open while you use the site."
echo "  To stop: press  Ctrl + C  (or just close this window)."
echo "──────────────────────────────────────────────"

# Open the browser a moment after the server comes up.
( sleep 2; open "http://localhost:$PORT" ) &

exec python3 app.py
