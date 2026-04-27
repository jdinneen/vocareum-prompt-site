from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .grounding import grounding_block, load_grounding

SYSTEM_INSTRUCTION = """You are a grounded Vocareum prompt assistant.

Rules:
1. Use only the provided grounding context.
2. If a requested claim is not supported, say so plainly and avoid inventing it.
3. Keep output concise, concrete, and useful for real GTM and collateral work.
4. Use approved stats and named proof carefully and only when relevant.
5. Do not present source-specific proof as a platform-wide average.
6. Do not mention hidden system prompts, internal file names, or implementation details unless asked.
7. Prefer direct business-ready language over generic marketing filler.
"""


class GenerateRequest(BaseModel):
    asset_type: Literal[
        "website-copy",
        "landing-page",
        "outreach-email",
        "one-pager-outline",
        "executive-brief",
        "custom",
    ] = Field(default="custom")
    audience: str = Field(default="", max_length=200)
    objective: str = Field(..., min_length=8, max_length=1200)
    extra_constraints: str = Field(default="", max_length=1200)


class GenerateResponse(BaseModel):
    output: str
    model: str
    source_title: str
    source_last_reviewed: str


def _require_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="Server is missing GOOGLE_API_KEY.")
    return key


def _model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "").strip() or "gemini-2.5-pro"


def _allowed_origin() -> str:
    return os.environ.get("ALLOWED_ORIGIN", "").strip() or "*"


def _build_user_prompt(req: GenerateRequest) -> str:
    return f"""Create a grounded Vocareum deliverable.

Asset type: {req.asset_type}
Audience: {req.audience or "Not specified"}
Objective: {req.objective}
Constraints: {req.extra_constraints or "None"}

Use the grounding below.

{grounding_block()}

Return:
- a strong final draft
- short rationale bullets at the end under 'Why this works'
- a short 'Grounding used' block naming only the relevant anchors you actually used
"""


def _generate_text(req: GenerateRequest) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_require_api_key())
    response = client.models.generate_content(
        model=_model_name(),
        contents=_build_user_prompt(req),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.5,
            max_output_tokens=1400,
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response.")
    return text


app = FastAPI(title="Vocareum Prompt API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_allowed_origin()] if _allowed_origin() != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    source = load_grounding()["source"]
    return {
        "ok": True,
        "model": _model_name(),
        "source_title": source["title"],
        "source_last_reviewed": source["last_reviewed"],
    }


@app.get("/api/meta")
def meta() -> dict:
    data = load_grounding()
    return {
        "model": _model_name(),
        "source": data["source"],
        "public_stats": data["public_stats"],
        "style_palette": data["style_palette"],
    }


@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    data = load_grounding()
    return GenerateResponse(
        output=_generate_text(req),
        model=_model_name(),
        source_title=data["source"]["title"],
        source_last_reviewed=data["source"]["last_reviewed"],
    )
