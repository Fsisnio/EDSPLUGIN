# Deploy on Render (Blueprint)

This project includes a [Render Blueprint](https://render.com/docs/infrastructure-as-code) for one-click deployment.

## Quick start

1. Push this repo to GitHub/GitLab/Bitbucket.
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**.
3. Connect your repository and select the branch containing `render.yaml`.
4. Render creates a single web service:
   - **edhs-webservice** – FastAPI + Streamlit in one container

## Post-deploy configuration

After the first deploy, configure these in the Render Dashboard:

### 1. DHS Program API key

- **Environment** → `DHS_PROGRAM_API_KEY`
- Get a key from [api.dhsprogram.com](https://api.dhsprogram.com/)

### 2. CORS origins

- **Environment** → `BACKEND_CORS_ORIGINS`
- Set to your service URL, e.g. `https://edhs-webservice-xxxx.onrender.com`
- Use comma-separated values for multiple origins

### 3. Optional: custom domain

- **Settings** → **Custom Domains**

## Architecture

| Component   | Port  | Description                                      |
|-------------|-------|--------------------------------------------------|
| Streamlit   | $PORT | Main UI (exposed)                                |
| FastAPI API | 8000  | Internal – called by dashboard at localhost:8000  |

Single container runs both; the dashboard connects to the API internally.

## Local development

```bash
# API
uvicorn edhs_core.main:app --reload

# Dashboard (in another terminal)
streamlit run web_dashboard/streamlit_app.py --server.port=8501
```

## Local single-service run (Docker)

```bash
docker build -f Dockerfile.webservice -t edhs-webservice .
docker run -p 8501:8501 -e PORT=8501 edhs-webservice
```
