# Run the EDHS dashboard (Streamlit). Start from project root.
# Requires: pip install -r web_dashboard/requirements.txt
# Start the API first in another terminal: uvicorn edhs_core.main:app --reload

cd "$(dirname "$0")/.."
python scripts/inject_streamlit_google_analytics.py
streamlit run web_dashboard/streamlit_app.py --server.port=8501
