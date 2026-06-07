#!/bin/bash
# Run Streamlit and expose it to your phone via a public tunnel URL.
set -e
cd "$(dirname "$0")"

URL_FILE="mobile_url.txt"

if ! lsof -iTCP:8501 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting Streamlit on http://localhost:8501 ..."
  ./venv/bin/streamlit run app.py &
  STREAMLIT_PID=$!
  sleep 3
else
  echo "Streamlit already running on port 8501."
  STREAMLIT_PID=""
fi

if [ ! -x "./bin/cloudflared" ]; then
  echo "Downloading cloudflared..."
  mkdir -p bin
  curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz" \
    | tar -xz -C bin
  chmod +x bin/cloudflared
fi

echo ""
echo "Starting tunnel..."
echo "The iPhone URL will appear below and be saved to $URL_FILE"
echo "Press Ctrl+C to stop the tunnel."
echo ""

cleanup() {
  if [ -n "$STREAMLIT_PID" ]; then
    kill "$STREAMLIT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

./bin/cloudflared tunnel --url http://localhost:8501 --no-autoupdate 2>&1 | while IFS= read -r line; do
  echo "$line"
  if echo "$line" | grep -q 'trycloudflare.com'; then
    url=$(echo "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
    if [ -n "$url" ]; then
      echo "$url" > "$URL_FILE"
      echo ""
      echo "============================================"
      echo "  Open on your iPhone:"
      echo "  $url"
      echo "  (saved to $URL_FILE)"
      echo "============================================"
      echo ""
    fi
  fi
done
