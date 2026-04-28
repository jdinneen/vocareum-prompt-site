# Vocareum Prompt Site

Minimal grounded assistant for Vocareum.

The current frontend is intentionally stripped down:

- one prompt box
- one grounded response area
- one live-source status line

The default UI sends a generic grounded request against the live product catalog context. It is meant to behave like a simple LLM surface that stays inside supported Vocareum source material.

The backend grounding stack uses:

- the live `Vocareum Product & Feature Catalog` Google Doc
- the live `Vocareum Approved Email Material` Google Doc
- the live `Example Collateral` Drive folder
- a governed local truth bundle generated from repo-approved source files

The stripped-down UI uses the generic grounded-answer path. The backend still contains older email and collateral-specific paths, but they are no longer surfaced in the main page.

It runs deterministic validation before returning output. The validator blocks:

- unsupported numbers
- disallowed named proof
- direct quotes
- unsupported claim sentences that are not sufficiently grounded in the selected source context

## Architecture

- `docs/`: static frontend for GitHub Pages
- `app/`: FastAPI backend for Cloud Run
- `app/grounding.py`: loads live Drive/Docs grounding plus the governed truth bundle
- `app/validation.py`: deterministic output validation
- `app/data/governed_truth_bundle.json`: governed local proof/stats bundle
- `scripts/build_governed_truth_bundle.py`: regenerates the local truth bundle from repo-approved source files

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
- the collateral folder and example files inside it

The Cloud Run project also needs `drive.googleapis.com` enabled.

## Local Run

```bash
cd sites/vocareum-prompt-site
PYTHONPATH=. /Users/jondinneen/Desktop/AIMktg/.venv/bin/python scripts/build_governed_truth_bundle.py
PYTHONPATH=. /Users/jondinneen/Desktop/AIMktg/.venv/bin/python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Tests

From the AIMktg repo root:

```bash
.venv/bin/python -m pytest sites/vocareum-prompt-site/tests -q
```

If you run the site repo standalone, install `pytest` into that local Python
environment before running the same `tests/` suite there.

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

- keep `window.APP_CONFIG.apiBaseUrl` in `docs/app.js` pointed at the live API
- publish `docs/` with GitHub Pages
