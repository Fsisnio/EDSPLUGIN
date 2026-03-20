# Deploy on Render (Blueprint)

This project includes a [Render Blueprint](https://render.com/docs/infrastructure-as-code) for one-click deployment.

## Quick start

1. Push this repo to GitHub/GitLab/Bitbucket.
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**.
3. Connect your repository and select the branch containing `render.yaml`.
4. Render will create two services:
   - **edhs-api** – FastAPI backend (Docker)
   - **edhs-dashboard** – Streamlit UI (Python)

## Post-deploy configuration

After the first deploy, configure these in the Render Dashboard:

### 1. DHS Program API key (edhs-api)

- **Environment** → `DHS_PROGRAM_API_KEY`
- Get a key from [api.dhsprogram.com](https://api.dhsprogram.com/)

### 2. CORS origins (edhs-api)

- **Environment** → `BACKEND_CORS_ORIGINS`
- Set to your dashboard URL, e.g. `https://edhs-dashboard-xxxx.onrender.com`
- Use comma-separated values for multiple origins

### 3. Optional: custom domain

- In each service → **Settings** → **Custom Domains**

## Architecture

| Service        | Runtime | Port | Description                    |
|----------------|---------|------|--------------------------------|
| edhs-api       | Docker  | 8000 | FastAPI backend, health at `/api/v1/health` |
| edhs-dashboard | Python  | $PORT | Streamlit app, connects to API via private network |

The dashboard uses `API_HOST` and `API_PORT` from the API service (Render private network) to connect without exposing the API publicly if desired.

## Local development

```bash
# API
uvicorn edhs_core.main:app --reload

# Dashboard (in another terminal)
streamlit run web_dashboard/streamlit_app.py --server.port=8501
```
