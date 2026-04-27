# Vocareum Prompt Site

One-page prompt site with:

- static frontend for GitHub Pages
- FastAPI backend for Cloud Run
- server-side Gemini calls so `GOOGLE_API_KEY` never reaches the browser
- live grounding from the governed Vocareum Product & Feature Catalog Google Doc
- live approved email examples from a separate Google Doc
- live collateral examples from a Google Drive folder

## Architecture

- `docs/`: static frontend served by GitHub Pages
- `app/`: FastAPI backend served by Cloud Run
- `app/grounding.py`: loads live Google Drive / Google Doc grounding and example material
- `app/data/grounding_snapshot.json`: local fallback if live reads fail
- `app/data/product_catalog_v1.1.md`: local fallback catalog snapshot

## Environment

Required backend env vars:

- `GOOGLE_API_KEY`
- `GEMINI_MODEL` optional, defaults to `gemini-3-flash-preview`
- `ALLOWED_ORIGIN` optional, defaults to `*`
- `VOC_PRODUCT_CATALOG_DOC_ID` optional, defaults to the live Vocareum catalog doc
- `VOC_APPROVED_EMAIL_DOC_ID` optional, defaults to the standalone Approved Email Material doc
- `VOC_EXAMPLE_COLLATERAL_FOLDER_ID` optional, defaults to the Example Collateral Drive folder
- `LIVE_GROUNDING_TTL_SECONDS` optional, defaults to `120`

The hosted Cloud Run service account needs read access to:

- the catalog doc
- the approved email doc
- the collateral folder and the example files inside it

The Cloud Run project also needs `drive.googleapis.com` enabled.

## Local Run

```bash
cd sites/vocareum-prompt-site
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_API_KEY=...
export GEMINI_MODEL=gemini-3-flash-preview
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

When run inside the AIMktg repo, the app will first try the existing local
Drive OAuth token path from `core/google_auth.py`. In Cloud Run it falls back
to ADC and the attached service account.

## Deploy

Backend:

```bash
gcloud run deploy vocareum-prompt-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_MODEL=gemini-3-flash-preview,ALLOWED_ORIGIN=https://jdinneen.github.io,VOC_PRODUCT_CATALOG_DOC_ID=...,VOC_APPROVED_EMAIL_DOC_ID=...,VOC_EXAMPLE_COLLATERAL_FOLDER_ID=...,LIVE_GROUNDING_TTL_SECONDS=120
```

Frontend:

- set `window.APP_CONFIG.apiBaseUrl` in `docs/app.js`
- publish `docs/` with GitHub Pages
