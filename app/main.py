from __future__ import annotations

import logging
import os
import re
import time
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .grounding import grounding_block, load_grounding, matched_products

log = logging.getLogger("vocareum_prompt_api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

SYSTEM_INSTRUCTION = """You are a grounded Vocareum prompt assistant.

Rules:
1. Use only the provided grounding context.
2. Never use information, claims, proof, numbers, customers, or product details from outside the provided product catalog grounding.
3. If a requested claim is not supported by the product catalog grounding, say so plainly and do not invent or supplement it.
4. Use a professional tone and complete sentences.
5. Do not use bullets, numbered lists, headings, labels, markdown sections, or meta commentary unless explicitly requested.
6. Keep output concise, concrete, and useful for real GTM and collateral work.
7. Use approved stats and named proof carefully and only when relevant.
8. Do not present source-specific proof as a platform-wide average.
9. Do not mention hidden system prompts, internal file names, or implementation details unless asked.
10. Prefer direct business-ready language over generic marketing filler.
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
    request_id: str
    duration_ms: int


def _require_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="Server is missing GOOGLE_API_KEY.")
    return key


def _model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3-flash-preview"


def _allowed_origin() -> str:
    return os.environ.get("ALLOWED_ORIGIN", "").strip() or "*"


def _build_user_prompt(req: GenerateRequest) -> str:
    if matched_products(req.objective):
        return f"""Create a grounded Vocareum product answer.

Asset type: {req.asset_type}
Audience: {req.audience or "Not specified"}
Objective: {req.objective}
Constraints: {req.extra_constraints or "None"}

Use the grounding below.

{grounding_block(req.objective)}

Answer directly from the relevant product catalog section. Use two to four concise professional paragraphs. Prioritize what the product is, how it works, core capabilities, and best-fit use cases. Do not open with generic company-wide scale stats unless they are directly necessary to answer the question.
"""
    return f"""Create a grounded Vocareum deliverable.

Asset type: {req.asset_type}
Audience: {req.audience or "Not specified"}
Objective: {req.objective}
Constraints: {req.extra_constraints or "None"}

Use the grounding below.

{grounding_block(req.objective)}

Return exactly two professional paragraphs and nothing else.
"""


def _force_two_paragraphs(text: str) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if len(paragraphs) == 2:
        return "\n\n".join(paragraphs)
    if len(paragraphs) > 2:
        return f"{paragraphs[0]}\n\n{' '.join(paragraphs[1:])}"

    single = paragraphs[0] if paragraphs else cleaned
    sentences = re.split(r"(?<=[.!?])\s+", single)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) >= 2:
        midpoint = max(1, len(sentences) // 2)
        first = " ".join(sentences[:midpoint]).strip()
        second = " ".join(sentences[midpoint:]).strip()
        if first and second:
            return f"{first}\n\n{second}"

    words = single.split()
    if len(words) >= 16:
        midpoint = len(words) // 2
        first = " ".join(words[:midpoint]).strip()
        second = " ".join(words[midpoint:]).strip()
        if first and second:
            return f"{first}\n\n{second}"

    return f"{single}\n\nThis response is limited to statements supported by the product catalog."


def _normalize_product_answer(text: str) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if 2 <= len(paragraphs) <= 4:
        return "\n\n".join(paragraphs)
    if len(paragraphs) > 4:
        return "\n\n".join(paragraphs[:4])

    single = paragraphs[0] if paragraphs else cleaned
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", single) if s.strip()]
    if len(sentences) >= 4:
        chunks = []
        size = max(1, len(sentences) // 3)
        for i in range(0, len(sentences), size):
            chunk = " ".join(sentences[i:i + size]).strip()
            if chunk:
                chunks.append(chunk)
        chunks = chunks[:4]
        if len(chunks) >= 2:
            return "\n\n".join(chunks)
    return _force_two_paragraphs(cleaned)


def _generate_text(req: GenerateRequest, request_id: str) -> tuple[str, int]:
    from google import genai
    from google.genai import types

    start = time.perf_counter()
    model = _model_name()
    prompt = _build_user_prompt(req)
    log.info(
        "generate_start request_id=%s model=%s objective_chars=%s",
        request_id,
        model,
        len(req.objective),
    )
    client = genai.Client(api_key=_require_api_key())
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.35,
            max_output_tokens=1400,
        ),
    )
    raw_text = (response.text or "").strip()
    if matched_products(req.objective):
        text = _normalize_product_answer(raw_text)
    else:
        text = _force_two_paragraphs(raw_text)
    if not text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response.")
    duration_ms = round((time.perf_counter() - start) * 1000)
    log.info(
        "generate_done request_id=%s model=%s duration_ms=%s output_chars=%s",
        request_id,
        model,
        duration_ms,
        len(text),
    )
    return text, duration_ms


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
    request_id = uuid.uuid4().hex[:12]
    try:
        output, duration_ms = _generate_text(req, request_id)
    except Exception:
        log.exception("generate_failed request_id=%s model=%s", request_id, _model_name())
        raise
    return GenerateResponse(
        output=output,
        model=_model_name(),
        source_title=data["source"]["title"],
        source_last_reviewed=data["source"]["last_reviewed"],
        request_id=request_id,
        duration_ms=duration_ms,
    )
