# Vocareum Prompt Site

One-page prompt site with:

- static frontend for GitHub Pages
- FastAPI backend for Cloud Run
- server-side Gemini calls so `GOOGLE_API_KEY` never reaches the browser
- grounding snapshot distilled from the governed Vocareum Product & Feature Catalog Google Doc

## Architecture

- `docs/`: static frontend served by GitHub Pages
- `app/`: FastAPI backend served by Cloud Run
- `app/data/grounding_snapshot.json`: checked-in grounding context used to build the Gemini prompt

## Environment

Required backend env vars:

- `GOOGLE_API_KEY`
- `GEMINI_MODEL` optional, defaults to `gemini-2.5-pro`
- `ALLOWED_ORIGIN` optional, defaults to `*`

## Local Run

```bash
cd sites/vocareum-prompt-site
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_API_KEY=...
export GEMINI_MODEL=gemini-2.5-pro
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Deploy

Backend:

```bash
gcloud run deploy vocareum-prompt-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_MODEL=gemini-2.5-pro,ALLOWED_ORIGIN=https://jdinneen.github.io
```

Frontend:

- set `window.APP_CONFIG.apiBaseUrl` in `docs/app.js`
- publish `docs/` with GitHub Pages
