#!/bin/sh
# Run API (internal) + Streamlit (exposed on $PORT) in one container
set -e

# API on 8000 - dashboard connects via localhost
uvicorn edhs_core.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Give API time to start
sleep 2

# Streamlit on Render's PORT (default 10000)
exec streamlit run web_dashboard/streamlit_app.py \
  --server.port="${PORT:-8501}" \
  --server.address=0.0.0.0 \
  --server.headless=true
