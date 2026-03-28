# EDHS dashboard — getting started

## Run the dashboard

From the **project root** (the folder that contains `edhs_core` and `web_dashboard`):

```bash
# 1. Start the API (first terminal)
uvicorn edhs_core.main:app --reload

# 2. Start the dashboard (second terminal)
cd "$(dirname "$0")/.."
python -m streamlit run web_dashboard/streamlit_app.py --server.port=8501 --server.headless=false
```

Or run Streamlit directly:

```bash
streamlit run web_dashboard/streamlit_app.py --server.port=8501
```

## If the page stays blank

1. **Hard refresh:** Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac).
2. **Check the URL:** open `http://localhost:8501` (try `127.0.0.1` if localhost misbehaves).
3. **Another browser:** try Chrome or Firefox.
4. **Disable extensions:** use a private window to test.
5. **Check the Streamlit terminal:** a Python error may appear at startup.
