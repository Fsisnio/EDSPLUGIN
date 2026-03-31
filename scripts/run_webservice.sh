#!/bin/sh
# Run API (internal) + Streamlit (exposed on $PORT) in one container
set -e

# API on 8000 - dashboard connects via loopback (same container only).
uvicorn edhs_core.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait until API answers (cold start / slow imports); Streamlit requests use this immediately on load
i=0
while [ "$i" -lt 45 ]; do
  if python -c "
import urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)
except Exception:
    raise SystemExit(1)
" 2>/dev/null; then
    break
  fi
  i=$((i + 1))
  sleep 1
done

# Streamlit on Render's PORT (default 10000)
exec streamlit run web_dashboard/streamlit_app.py \
  --server.port="${PORT:-8501}" \
  --server.address=0.0.0.0 \
  --server.headless=true
