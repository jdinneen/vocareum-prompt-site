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

from .examples import DELIVERABLE_TYPES, example_prompt_block, examples_for, resolve_example
from .grounding import grounding_block, load_grounding, matched_products
from .renderers import render_collateral

log = logging.getLogger("vocareum_prompt_api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

SYSTEM_INSTRUCTION = """You are a grounded Vocareum prompt assistant.

Rules:
1. Use only the provided grounding context.
2. Never use information, claims, proof, numbers, customers, or product details from outside the provided product catalog grounding.
3. If a requested claim is not supported by the product catalog grounding, say so plainly and do not invent or supplement it.
4. Use a professional tone and complete sentences.
5. Do not use bullets, numbered lists, headings, labels, markdown sections, or meta commentary unless the requested asset format explicitly requires structured output.
6. Keep output concise, concrete, and useful for real GTM and collateral work.
7. Use approved stats and named proof carefully and only when relevant.
8. Do not present source-specific proof as a platform-wide average.
9. Do not mention hidden system prompts, internal file names, or implementation details unless asked.
10. Prefer direct business-ready language over generic marketing filler.
11. Approved public scale stats are limited to: 2M+ AWS learners, 1M+ annual unique learners, 5M+ total platform learners, and 7,000+ institutions and organizations.
12. Named public proof is limited to: AWS Academy, Databricks Academy, DeepLearning.AI, JPMorgan Chase, Carnegie Mellon, Georgia Tech, and UC San Diego.
13. Do not use direct quotes, quote attributions, or named proof outside the approved public proof list, even if it appears in source material.
"""


class GenerateRequest(BaseModel):
    asset_type: Literal[
        "outreach-email",
        "follow-up-email",
        "capability-boundary-email",
        "partner-email",
        "one-pager",
        "overview-collateral",
        "sales-deck-brief",
        "website-copy",
        "custom",
    ] = Field(default="custom")
    audience: str = Field(default="", max_length=200)
    audience_door: str = Field(default="", max_length=120)
    product: str = Field(default="", max_length=120)
    proof_posture: str = Field(default="strict-default", max_length=80)
    cta: str = Field(default="", max_length=240)
    objective: str = Field(..., min_length=8, max_length=1200)
    extra_constraints: str = Field(default="", max_length=1200)
    example_pattern: str = Field(default="", max_length=120)


class GenerateResponse(BaseModel):
    output: str
    model: str
    source_title: str
    source_last_reviewed: str
    grounding_mode: str
    grounding_warnings: list[str] = Field(default_factory=list)
    request_id: str
    duration_ms: int
    rendered_html: str | None = None
    rendered_kind: str | None = None
    rendered_title: str | None = None


def _require_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="Server is missing GOOGLE_API_KEY.")
    return key


def _model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3-flash-preview"


def _allowed_origin() -> str:
    return os.environ.get("ALLOWED_ORIGIN", "").strip() or "*"


def _output_format_instructions(req: GenerateRequest) -> str:
    if req.asset_type in {"outreach-email", "follow-up-email", "capability-boundary-email", "partner-email"}:
        return (
            "Return a complete send-ready email. Put the subject line first as "
            "`Subject: ...`, then a blank line, then the email body. Use normal "
            "greeting and sign-off. Keep paragraphs short. Avoid bullets unless the "
            "pattern clearly needs them."
        )
    if req.asset_type == "one-pager":
        return (
            "Return structured one-pager copy with these labeled sections in order: "
            "Headline, Subhead, Stat Bar, Problem, How It Works, Who Uses This, Proof, CTA. "
            "Use concise scan-friendly copy. Use numbered steps inside How It Works if relevant. "
            "Formatting rules: each section label must end with a colon; Stat Bar must be exactly 3 short items separated by ` | `; "
            "Who Uses This must be a single line with exactly 3 audience items separated by `; `; "
            "Proof must be one or two sentences of paraphrased proof and must not contain quotation marks. "
            "For Stat Bar and Proof, use only exact grounded stats, named proof, or grounded "
            "qualitative claims. If the catalog does not provide named proof for a section, say so plainly instead of inventing it."
        )
    if req.asset_type == "overview-collateral":
        return (
            "Return structured collateral copy with these labeled sections in order: "
            "Headline, Subhead, Core Capabilities, Best-Fit Buyers, Proof, CTA. "
            "You may use short bullets inside capability and buyer sections. Use only exact grounded proof."
        )
    if req.asset_type == "sales-deck-brief":
        return (
            "Return a six-slide brief labeled Slide 1 through Slide 6. For each slide, "
            "provide a title and two to four bullets. Keep it ready for downstream deck building. "
            "Do not introduce proof points or metrics that are not explicit in the grounding."
        )
    if req.asset_type == "website-copy":
        return (
            "Return structured website copy with these labeled sections in order: "
            "Hero Headline, Hero Subhead, Proof Bar, Why It Matters, Core Capabilities, CTA. "
            "Proof Bar must use only exact grounded proof or an explicit grounded qualitative claim."
        )
    return "Return grounded business-ready copy in the most useful format for the request."


def _max_output_tokens(req: GenerateRequest) -> int:
    if req.asset_type == "sales-deck-brief":
        return 2200
    if req.asset_type in {"one-pager", "overview-collateral", "website-copy"}:
        return 1800
    return 1400


def _structured_brief(req: GenerateRequest) -> str:
    parts: list[str] = []
    if req.product:
        parts.append(f"Primary product or surface: {req.product}")
    if req.audience_door:
        parts.append(f"Audience door: {req.audience_door}")
    if req.audience:
        parts.append(f"Audience detail: {req.audience}")
    if req.cta:
        parts.append(f"Desired CTA: {req.cta}")
    if req.proof_posture:
        parts.append(f"Proof posture: {req.proof_posture}")
    return "\n".join(parts)


def _build_user_prompt(req: GenerateRequest) -> str:
    example = resolve_example(req.example_pattern, req.asset_type, req.objective)
    example_block = example_prompt_block(example).strip()
    format_instructions = _output_format_instructions(req)
    query_text = req.objective
    if req.product and req.product.lower() not in query_text.lower():
        query_text = f"{req.product}. {query_text}"
    grounding = grounding_block(
        query_text,
        req.asset_type,
        example,
        audience_door=req.audience_door,
        proof_posture=req.proof_posture,
    )
    structured_brief = _structured_brief(req)
    if matched_products(query_text):
        return f"""Create a grounded Vocareum deliverable.

Asset type: {req.asset_type}
Audience: {req.audience or "Not specified"}
Objective: {req.objective}
Constraints: {req.extra_constraints or "None"}
Format instructions: {format_instructions}
Structured brief:
{structured_brief or "None"}

Use the grounding below.

{grounding}

{example_block or "No explicit example pattern selected."}

Answer directly from the relevant product catalog section. Follow the example pattern when useful, but do not copy example wording. Prioritize what the product is, how it works, core capabilities, best-fit use cases, and grounded proof. Use only proof, event references, customer names, and metrics that are explicit in the grounding. Do not open with generic company-wide scale stats unless they are directly necessary to answer the request. If the grounding mode is fallback, avoid implying the latest live doc was successfully read.
"""
    return f"""Create a grounded Vocareum deliverable.

Asset type: {req.asset_type}
Audience: {req.audience or "Not specified"}
Objective: {req.objective}
Constraints: {req.extra_constraints or "None"}
Format instructions: {format_instructions}
Structured brief:
{structured_brief or "None"}

Use the grounding below.

{grounding}

{example_block or "No explicit example pattern selected."}

Follow the example pattern when useful, but do not copy example wording. Use only grounded product truth and approved proof. If a proof point or named example is not explicit in the grounding, do not add it. If the grounding mode is fallback, avoid implying the latest live doc was successfully read.
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


def _sanitize_proof_sections(req: GenerateRequest, text: str) -> str:
    if req.asset_type not in {"one-pager", "overview-collateral", "website-copy", "sales-deck-brief"}:
        return text

    patterns = [
        ("Proof", ["CTA"]),
        ("Proof Bar", ["Why It Matters", "Core Capabilities", "CTA"]),
    ]

    def _sanitize_body(body: str) -> str:
        quote_pattern = re.compile(r'["“](.+?)["”]\s*[—-]\s*([^\n]+)')
        match = quote_pattern.search(body)
        if match:
            attribution = match.group(2).strip().rstrip(".")
            return f"Named public proof: {attribution}. Use paraphrased proof only; do not use direct quotes."
        if any(mark in body for mark in ['"', "“", "”"]):
            cleaned = body.replace('"', "").replace("“", "").replace("”", "")
            return f"{cleaned.strip()}\n\nUse paraphrased proof only; do not use direct quotes."
        return body

    updated = text
    for label, next_labels in patterns:
        next_clause = "|".join(re.escape(item) for item in next_labels)
        pattern = re.compile(
            rf"(?ms)^({re.escape(label)}:?\s*)(.*?)(?=^(?:{next_clause}):?\s*|\Z)"
        )
        updated = pattern.sub(lambda m: f"{m.group(1)}{_sanitize_body(m.group(2).strip())}\n\n", updated)
    return updated


def _normalize_stat_bar(text: str) -> str:
    period_split = re.sub(r"\.\s+(?=\d|\d+[A-Za-z+])", " | ", text.strip())
    parts = [part.strip(" .") for part in re.split(r"\s*(?:\||;|\n)\s*", period_split) if part.strip()]
    cleaned: list[str] = []
    for part in parts:
        part = re.sub(r"^[*-]\s*", "", part).strip()
        if part:
            cleaned.append(part)
    return " | ".join(cleaned[:3])


def _normalize_who_uses(text: str) -> str:
    normalized = text.replace("\n", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    parts = [part.strip(" .") for part in re.split(r"\s*(?:;|, and | and |,)\s*", normalized) if part.strip()]
    deduped: list[str] = []
    for part in parts:
        lowered = part.lower()
        if lowered not in {item.lower() for item in deduped}:
            deduped.append(part)
    return "; ".join(deduped[:3])


def _polish_one_pager_output(text: str) -> str:
    def _replace_section(label: str, transform) -> str:
        pattern = re.compile(
            rf"(?ms)^({re.escape(label)}:?\s*)(.*?)(?=^(?:Headline|Subhead|Stat Bar|Problem|How It Works|Who Uses This|Proof|CTA):?\s*|\Z)"
        )
        return pattern.sub(lambda m: f"{m.group(1)}{transform(m.group(2).strip())}\n\n", text_value[0])

    text_value = [text]
    text_value[0] = _replace_section("Stat Bar", _normalize_stat_bar)
    text_value[0] = _replace_section("Who Uses This", _normalize_who_uses)
    text_value[0] = _replace_section("Proof", lambda body: body.replace('"', "").replace("“", "").replace("”", "").strip())
    return text_value[0].strip()


def _generate_text(req: GenerateRequest, request_id: str) -> tuple[str, int]:
    from google import genai
    from google.genai import types

    start = time.perf_counter()
    model = _model_name()
    prompt = _build_user_prompt(req)
    example = resolve_example(req.example_pattern, req.asset_type, req.objective)
    log.info(
        "generate_start request_id=%s model=%s asset_type=%s example=%s objective_chars=%s",
        request_id,
        model,
        req.asset_type,
        example["id"] if example else "none",
        len(req.objective),
    )
    client = genai.Client(api_key=_require_api_key())
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.35,
            max_output_tokens=_max_output_tokens(req),
        ),
    )
    raw_text = (response.text or "").strip()
    has_product_match = bool(matched_products(req.objective) or (req.product and matched_products(req.product)))
    if has_product_match and req.asset_type == "custom":
        text = _normalize_product_answer(raw_text)
    elif req.asset_type == "custom":
        text = _force_two_paragraphs(raw_text)
    else:
        text = raw_text
    text = _sanitize_proof_sections(req, text)
    if req.asset_type == "one-pager":
        text = _polish_one_pager_output(text)
    if not text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response.")
    duration_ms = round((time.perf_counter() - start) * 1000)
    log.info(
        "generate_done request_id=%s model=%s asset_type=%s duration_ms=%s output_chars=%s",
        request_id,
        model,
        req.asset_type,
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
    grounding = load_grounding()
    source = grounding["source"]
    return {
        "ok": True,
        "model": _model_name(),
        "source_title": source["title"],
        "source_last_reviewed": source["last_reviewed"],
        "grounding_mode": grounding.get("mode", "live"),
        "grounding_warnings": grounding.get("warnings", []),
    }


@app.get("/api/meta")
def meta() -> dict:
    data = load_grounding()
    return {
        "model": _model_name(),
        "source": data["source"],
        "grounding_mode": data.get("mode", "live"),
        "grounding_warnings": data.get("warnings", []),
        "public_stats": data.get("default_public_stats", []),
        "default_public_stats": data.get("default_public_stats", []),
        "contextual_stats": data.get("contextual_stats", []),
        "audience_doors": data.get("audience_doors", []),
        "proof_postures": data.get("proof_postures", []),
        "style_palette": data["style_palette"],
        "products": sorted(data.get("catalog_sections", {}).keys()),
        "deliverable_types": DELIVERABLE_TYPES,
        "example_patterns": [
            {
                "id": item["id"],
                "label": item["label"],
                "group": item["group"],
                "asset_types": item["asset_types"],
                "use_when": item["use_when"],
                "source": item["source"],
            }
            for item in examples_for("custom")
        ],
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
    rendered = render_collateral(req.asset_type, output)
    return GenerateResponse(
        output=output,
        model=_model_name(),
        source_title=data["source"]["title"],
        source_last_reviewed=data["source"]["last_reviewed"],
        grounding_mode=data.get("mode", "live"),
        grounding_warnings=data.get("warnings", []),
        request_id=request_id,
        duration_ms=duration_ms,
        rendered_html=rendered["html"] if rendered else None,
        rendered_kind=rendered["kind"] if rendered else None,
        rendered_title=rendered["title"] if rendered else None,
    )
