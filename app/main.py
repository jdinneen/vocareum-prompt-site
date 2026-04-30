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

from .examples import DELIVERABLE_TYPES, example_prompt_block, resolve_example
from .grounding import grounding_block, load_grounding, matched_products, selected_grounding_text
from .renderers import render_collateral
from .validation import validate_output

log = logging.getLogger("vocareum_prompt_api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)


DISALLOWED_ONE_PAGER_PROOF_PATTERNS = (
    re.compile(r"\bnairr\b", re.IGNORECASE),
)

HIGH_SIGNAL_ONE_PAGER_PROOFS = {
    "University of Michigan",
    "UC San Diego / GPS",
    "GPS UC San Diego",
    "AWS Academy",
    "Databricks Academy",
    "Databricks",
}

ONE_PAGER_LOGO_LIBRARY = {
    "University of Michigan": {
        "name": "University of Michigan",
        "kind": "customer",
        "url": "https://www.vocareum.com/wp-content/uploads/2026/03/University-of-Michigan.png",
    },
    "UC San Diego / GPS": {
        "name": "UC San Diego",
        "kind": "customer",
        "url": "https://www.vocareum.com/wp-content/uploads/2026/03/University_of_California_San_Diego_logo.svg",
    },
    "GPS UC San Diego": {
        "name": "UC San Diego",
        "kind": "customer",
        "url": "https://www.vocareum.com/wp-content/uploads/2026/03/University_of_California_San_Diego_logo.svg",
    },
    "AWS Academy": {
        "name": "AWS",
        "kind": "partner",
        "url": "https://www.vocareum.com/wp-content/uploads/2026/03/Amazon_Web_Services_Logo.svg",
    },
    "Databricks Academy": {
        "name": "Databricks",
        "kind": "partner",
        "url": "https://www.vocareum.com/wp-content/uploads/2026/03/databricks-logo.webp",
    },
    "Databricks": {
        "name": "Databricks",
        "kind": "partner",
        "url": "https://www.vocareum.com/wp-content/uploads/2026/03/databricks-logo.webp",
    },
}

ONE_PAGER_PROOF_LIBRARY = {
    "University of Michigan": {
        "organization": "University of Michigan",
        "use_case": "Expanded AI Gateway and AI Notebook campus-wide for secure generative AI access and scaled lab delivery.",
        "what_it_proves": "Vocareum can deliver governed AI access and hands-on infrastructure at major-university scale.",
        "source_url": "https://www.vocareum.com/university-of-michigan-partnership/",
        "priority": 100,
        "tags": {"ai gateway", "ai notebook", "gpu & cpu compute", "higher education", "governed ai"},
    },
    "UC San Diego / GPS": {
        "organization": "UC San Diego",
        "use_case": "AI Compass supported math-prep instruction with 80k+ graded responses, 16.9k tutor questions, and failure-rate movement from 35.6% to 11.4% vs prior cohort.",
        "what_it_proves": "Vocareum can improve learner support and faculty visibility inside a live academic workflow, not just a lab sandbox.",
        "source_url": "https://www.vocareum.com/gps-ucsd/",
        "priority": 95,
        "tags": {"ai compass", "simulations", "higher education", "teaching and learning"},
    },
    "GPS UC San Diego": {
        "organization": "UC San Diego",
        "use_case": "AI Compass supported math-prep instruction with 80k+ graded responses, 16.9k tutor questions, and failure-rate movement from 35.6% to 11.4% vs prior cohort.",
        "what_it_proves": "Vocareum can improve learner support and faculty visibility inside a live academic workflow, not just a lab sandbox.",
        "source_url": "https://www.vocareum.com/gps-ucsd/",
        "priority": 95,
        "tags": {"ai compass", "simulations", "higher education", "teaching and learning"},
    },
    "AWS Academy": {
        "organization": "AWS Academy",
        "use_case": "Hands-on cloud learning with scalable lab delivery for a very large learner base.",
        "what_it_proves": "Vocareum is trusted to power governed, production-grade cloud learning at scale.",
        "source_url": "https://www.vocareum.com/aws-academy/",
        "priority": 86,
        "tags": {"cloud labs", "on-the-fly labs", "aws", "higher education", "enterprise"},
    },
    "Databricks Academy": {
        "organization": "Databricks Academy",
        "use_case": "Standardized hands-on learning across asynchronous, instructor-led, and bootcamp delivery models.",
        "what_it_proves": "Vocareum fits partner-led enablement programs that need governed, repeatable lab delivery.",
        "source_url": "https://www.databricks.com/blog/boost-your-data-ai-skills-our-latest-offerings-databricks-academy-labs-and-blended-learning",
        "priority": 84,
        "tags": {"databases", "ai notebook", "enterprise", "enablement", "bootcamps"},
    },
    "Databricks": {
        "organization": "Databricks",
        "use_case": "Standardized hands-on learning across asynchronous, instructor-led, and bootcamp delivery models.",
        "what_it_proves": "Vocareum fits partner-led enablement programs that need governed, repeatable lab delivery.",
        "source_url": "https://www.databricks.com/blog/boost-your-data-ai-skills-our-latest-offerings-databricks-academy-labs-and-blended-learning",
        "priority": 84,
        "tags": {"databases", "ai notebook", "enterprise", "enablement", "bootcamps"},
    },
    "Georgia Tech": {
        "organization": "Georgia Tech",
        "use_case": "AI and data courses using notebook-based assignments, LMS integration, and GPU access.",
        "what_it_proves": "Vocareum can support large-scale, faculty-led AI course delivery with real environments and assessment.",
        "source_url": "https://www.vocareum.com/georgia-tech-case-study/",
        "priority": 70,
        "tags": {"ai notebook", "gpu & cpu compute", "higher education"},
    },
    "Iowa State": {
        "organization": "Iowa State University",
        "use_case": "AI Notebook for MLOps and generative AI micro-credentials with secure auto-grading.",
        "what_it_proves": "Vocareum can support advanced AI course delivery in governed notebook environments.",
        "source_url": "https://www.vocareum.com/iowa-state-university/",
        "priority": 38,
        "tags": {"ai notebook", "higher education"},
    },
    "National Research Platform": {
        "organization": "National Research Platform",
        "use_case": "Governed research-computing delivery for university partners evaluating shared AI infrastructure.",
        "what_it_proves": "Vocareum can participate in multi-institution compute programs when governed access is the core requirement.",
        "source_url": "https://www.vocareum.com/nrp/",
        "priority": 28,
        "tags": {"gpu & cpu compute", "ai gateway", "research"},
    },
}

DEFAULT_ONE_PAGER_LOGO_STRIP = [
    ONE_PAGER_LOGO_LIBRARY["University of Michigan"],
    ONE_PAGER_LOGO_LIBRARY["UC San Diego / GPS"],
    ONE_PAGER_LOGO_LIBRARY["AWS Academy"],
    ONE_PAGER_LOGO_LIBRARY["Databricks"],
]

DEFAULT_ONE_PAGER_QUOTE = {
    "text": "We've standardized on Vocareum's education technology platform for our asynchronous, instructor-led and bootcamp courses.",
    "attribution": "Rochana Golani",
    "title": "GVP, Learning & Enablement, Databricks",
    "source_url": "https://www.databricks.com/blog/boost-your-data-ai-skills-our-latest-offerings-databricks-academy-labs-and-blended-learning",
}

ONE_PAGER_DEFAULT_BUYERS = {
    "AI Gateway": [
        "IT and academic leaders governing AI access",
        "Teaching and learning teams embedding AI into courses",
        "Program owners managing policy, spend, and usage visibility",
    ],
    "GPU & CPU Compute": [
        "Research-computing leaders scaling advanced workloads",
        "Faculty and lab teams that need controlled GPU access",
        "Program owners balancing access, budgets, and uptime",
    ],
    "AI Notebook": [
        "Course teams delivering applied AI and data labs",
        "Faculty building notebook-based assignments",
        "Program owners standardizing governed notebook environments",
    ],
    "AI Compass": [
        "Teaching teams improving learner readiness before core coursework",
        "Academic leaders closing skills gaps with live AI support",
        "Program owners that need faculty-facing learning visibility",
    ],
    "Simulations": [
        "Learning product teams building scenario-based practice",
        "Program owners rehearsing judgment and workflow readiness",
        "Training teams that need safe practice before live systems",
    ],
    "Cloud Labs": [
        "Training and enablement teams running hands-on cloud learning",
        "Platform teams that need predictable, governed lab delivery",
        "Program owners scaling workshops without environment drift",
    ],
    "On-the-Fly Labs": [
        "Solutions and enablement teams building labs quickly",
        "Workshop owners who need governed live environments fast",
        "Program teams that want reusable hands-on lab delivery",
    ],
}


class GenerateRequest(BaseModel):
    asset_type: Literal["grounded-answer", "outbound-email", "reply-email", "sales-collateral", "one-pager", "sales-deck-brief"] = Field(default="outbound-email")
    audience: str = Field(default="", max_length=200)
    product: str = Field(default="", max_length=120)
    objective: str = Field(..., min_length=8, max_length=8000)
    extra_constraints: str = Field(default="", max_length=1500)


class GenerateResponse(BaseModel):
    output: str
    model: str
    source_title: str
    source_last_reviewed: str
    source_doc_url: str | None = None
    source_modified_time: str | None = None
    source_version: str | None = None
    source_checked_at: str | None = None
    grounding_mode: str
    grounding_warnings: list[str] = Field(default_factory=list)
    request_id: str
    duration_ms: int
    rendered_html: str | None = None
    rendered_kind: str | None = None
    rendered_title: str | None = None
    content_packet: dict | None = None
    quality_report: dict = Field(default_factory=dict)


class ImproveRequest(BaseModel):
    request: GenerateRequest
    current_output: str = Field(..., min_length=20, max_length=20000)
    rating: int = Field(default=3, ge=1, le=5)
    notes: str = Field(default="", max_length=2000)


def _source_response_fields(data: dict) -> dict:
    source = data["source"]
    return {
        "source_title": source["title"],
        "source_last_reviewed": source["last_reviewed"],
        "source_doc_url": source.get("doc_url"),
        "source_modified_time": source.get("modified_time"),
        "source_version": source.get("version"),
        "source_checked_at": source.get("checked_at"),
    }


def _meta_payload(data: dict) -> dict:
    truth_bundle = data["truth_bundle"]
    return {
        "model": _model_name(),
        "source": data["source"],
        "grounding_mode": data.get("mode", "live"),
        "grounding_warnings": data.get("warnings", []),
        "default_public_stats": truth_bundle.get("default_public_stats", []),
        "style_palette": data["style_palette"],
        "products": sorted(item for item in data.get("catalog_sections", {}).keys() if not item.startswith("All ")),
        "deliverable_types": DELIVERABLE_TYPES,
        "cache_loaded_at": data.get("cache_loaded_at"),
        "cache_ttl_seconds": data.get("cache_ttl_seconds"),
    }


def _require_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="Server is missing GOOGLE_API_KEY.")
    return key


def _model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3-flash-preview"


def _allowed_origin() -> str:
    return os.environ.get("ALLOWED_ORIGIN", "").strip() or "*"


def _system_instruction(truth_bundle: dict) -> str:
    public_stats = ", ".join(truth_bundle.get("default_public_stats", []))
    named_proof = ", ".join(truth_bundle.get("approved_named_proof", []))
    return f"""You are a grounded Vocareum GTM writing assistant.

Rules:
1. Use only the provided grounding context and user-supplied thread or brief.
2. Never use product details, customer proof, numbers, or claims from outside the provided grounding.
3. If a claim is not supported, leave it out or say so plainly.
4. Write in direct business-ready language. Avoid filler, hype, and generic marketing language.
5. Do not use direct quotes.
6. Approved default public stats: {public_stats}.
7. If you use an approved public stat, preserve its exact wording and scope from the grounding. Do not rewrite abbreviations like `2M+` into `2 million`.
8. Approved named public proof is limited to: {named_proof}.
9. Do not present source-specific proof as platform-wide average proof.
10. Remove generic bridge sentences unless they are directly supported by the grounding.
11. Stay inside the user's requested task. If they ask a question, answer it directly. If they ask for copy, write only the requested copy.
12. Do not mention system prompts, hidden rules, or implementation details.
13. Lead with specific product capabilities and use cases, not platform-wide stats. Stats are supporting evidence, not the lead. Never list stats as bullet-point filler.
14. When asked for an email, write a substantive send-ready email focused on product value for the recipient, not a stat summary.
"""


def _output_format_instructions(req: GenerateRequest) -> str:
    if req.asset_type == "grounded-answer":
        return (
            "Return the most useful grounded response for the request. "
            "Answer directly in plain business English. "
            "Lead with specific product capabilities and use cases, not platform-wide stats. "
            "Only include approved public stats if they directly support the point being made — never list stats as filler. "
            "If the user asks for an email, write a real send-ready email with a Subject line, a substantive body about the product, and a clear next step. "
            "Do not force email, one-pager, or deck structure unless the user explicitly asks for it."
        )
    if req.asset_type == "outbound-email":
        return (
            "Return a complete send-ready outbound email. Put the subject line first as `Subject: ...`, "
            "then a blank line, then the email body. Keep paragraphs short. No bullets unless strictly needed."
        )
    if req.asset_type == "reply-email":
        return (
            "Return a complete send-ready reply email. Assume the brief may include a pasted thread or incoming email. "
            "Infer the actual ask from that thread, answer directly, and return only the reply. Put the subject line first as "
            "`Subject: ...`, then a blank line, then the email body. If the thread contains more than one ask, answer all of them in the reply."
        )
    if req.asset_type == "one-pager":
        return (
            "Return a structured one-pager with ALL of these labeled sections in this exact order. "
            "Every section is REQUIRED — do not omit any.\n\n"
            "Audience: one short audience eyebrow beginning with 'For ...'\n"
            "Headline: one strong value-proposition line\n"
            "Subhead: 1-2 sentences expanding the headline\n"
            "Stat Bar: 3-4 entries separated by | in the format 'value - label' (e.g. '2M+ - AWS learners')\n"
            "Problem: 2-3 sentences on the pain point this solves\n"
            "How It Works: 3 short actions separated by |\n"
            "Who Uses This: 1-3 specific buyer or operator entries separated by |. Do not use generic labels like learners, researchers, business teams, or technical teams.\n"
            "Proof: 1-2 approved named public proof entries separated by | in the format 'reference - what it proves'. If no approved named public proof exists, write 'None'.\n"
            "CTA: one clear next-step sentence\n\n"
            "Put each section label at the start of its own line followed by the content. "
            "Keep copy concise and scan-friendly. Use only grounded proof. "
            "If the brief names a company, institution, or partner, keep that audience explicit in the Subhead and Who Uses This sections instead of broadening it into generic sectors. "
            "When a named audience is provided, make the first Who Uses This entry begin with that exact audience name. "
            "Do not use source metadata, review dates, catalog names, workflow/category placeholders, or NAIRR references as proof."
        )
    if req.asset_type == "sales-deck-brief":
        return (
            "Return a 6-slide presentation outline. Label each slide as 'Slide N: Title' on its own line, "
            "followed by 3-5 bullet points per slide. Suggested slide flow: "
            "Slide 1: Opening hook with buyer context. "
            "Slide 2: Problem or market challenge. "
            "Slide 3: Solution overview. "
            "Slide 4: Core capabilities or differentiators. "
            "Slide 5: Proof and scale. "
            "Slide 6: Call to action and next steps. "
            "Use concise bullet language. Use only grounded proof."
        )
    return (
        "Return structured sales collateral copy with these labeled sections in order: "
        "Headline, Subhead, Core Capabilities, Best-Fit Buyers, Proof, CTA. "
        "Put each section on its own line with a blank line between sections. "
        "Use concise scan-friendly copy. Use only grounded proof. Proof must be paraphrased and must not contain quotation marks."
    )


def _max_output_tokens(req: GenerateRequest) -> int:
    if req.asset_type == "grounded-answer":
        return 1400
    if req.asset_type == "one-pager":
        return 3200
    if req.asset_type == "sales-collateral":
        return 1800
    if req.asset_type == "sales-deck-brief":
        return 2200
    if req.asset_type == "reply-email":
        return 1600
    return 1200


def _structured_brief(req: GenerateRequest) -> str:
    parts: list[str] = []
    product = _resolved_product(req)
    if product:
        parts.append(f"Primary product or surface: {product}")
    audience = _resolved_audience(req)
    if audience:
        parts.append(f"Audience: {audience}")
    return "\n".join(parts)


def _objective_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9@.+-]{2,}", text)


SPECIFICITY_STOPWORDS = {
    "about",
    "aimed",
    "asset",
    "based",
    "brief",
    "build",
    "collateral",
    "concise",
    "content",
    "create",
    "follow",
    "include",
    "need",
    "one",
    "pager",
    "packet",
    "sentences",
    "short",
    "sided",
    "this",
    "two",
    "want",
}
AUDIENCE_CUE_PATTERNS = (
    re.compile(r"\baimed at\s+(.+?)(?=\b(?:for|aimed at|targeted at|targeting)\b|[,.;]|$)", re.IGNORECASE),
    re.compile(r"\btargeted at\s+(.+?)(?=\b(?:for|aimed at|targeted at|targeting)\b|[,.;]|$)", re.IGNORECASE),
    re.compile(r"\btargeting\s+(.+?)(?=\b(?:for|aimed at|targeted at|targeting)\b|[,.;]|$)", re.IGNORECASE),
    re.compile(r"\bfor\s+(.+?)(?=\b(?:for|aimed at|targeted at|targeting)\b|[,.;]|$)", re.IGNORECASE),
)
GENERIC_AUDIENCE_TOKENS = {
    "a",
    "an",
    "and",
    "asset",
    "brief",
    "build",
    "collateral",
    "concise",
    "content",
    "create",
    "deck",
    "need",
    "one",
    "page",
    "pager",
    "packet",
    "sales",
    "sentence",
    "sentences",
    "sheet",
    "sheeter",
    "short",
    "side",
    "sided",
    "simulation",
    "simulations",
    "the",
    "this",
    "two",
    "write",
}


def _normalized_phrase(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _infer_audience_from_text(text: str) -> str:
    candidates: list[tuple[int, str]] = []
    for pattern in AUDIENCE_CUE_PATTERNS:
        for match in pattern.finditer(text):
            candidate = re.sub(r"\s+", " ", match.group(1)).strip(" ,.;:-")
            candidate = re.sub(r"^(?:a|an|the)\s+", "", candidate, flags=re.IGNORECASE).strip()
            if candidate:
                candidates.append((match.start(), candidate))

    for _position, candidate in sorted(candidates, key=lambda item: item[0], reverse=True):
        normalized = _normalized_phrase(candidate)
        if len(normalized) < 3:
            continue
        if matched_products(candidate):
            continue
        tokens = [token for token in normalized.split() if token]
        if tokens and all(token in GENERIC_AUDIENCE_TOKENS for token in tokens):
            continue
        return candidate
    return ""


def _resolved_audience(req: GenerateRequest) -> str:
    return req.audience.strip() or _infer_audience_from_text(req.objective)


def _resolved_product(req: GenerateRequest) -> str:
    explicit = req.product.strip()
    if explicit:
        return explicit
    inferred = matched_products(req.objective)
    return ", ".join(inferred)


def _specificity_score(req: GenerateRequest, output: str) -> tuple[int, list[str]]:
    output_lower = output.lower()
    signals: list[str] = []
    hits = 0

    product = _resolved_product(req)
    product_names = matched_products(f"{product} {req.objective}")
    if not product_names and product:
        product_names = [item.strip() for item in product.split(",") if item.strip()]
    if product_names and any(name.lower() in output_lower for name in product_names):
        hits += 2
        signals.append("named product match")

    specificity_source = _resolved_audience(req) or req.objective
    objective_terms: list[str] = []
    for token in _objective_tokens(specificity_source):
        lowered = token.lower()
        if len(lowered) < 5 or lowered in SPECIFICITY_STOPWORDS:
            continue
        if lowered not in objective_terms:
            objective_terms.append(lowered)
    matched_terms = [token for token in objective_terms[:8] if token in output_lower]
    if len(matched_terms) >= 2:
        hits += 2
        signals.append("audience/context term match")

    if len(output.split()) > 50:
        hits += 1
        signals.append("substantive length")

    score = max(1, min(5, hits + 1))
    return score, signals


def _brief_needs_more_detail(req: GenerateRequest) -> dict | None:
    objective = req.objective.strip()
    lower = objective.lower()
    tokens = _objective_tokens(objective)
    audience = _resolved_audience(req)
    missing: list[str] = []
    examples: list[str] = []

    # Count product and audience as context — a short objective is fine if
    # the structured fields carry the weight.
    effective_tokens = len(tokens)
    if req.product:
        effective_tokens += 2
    if audience:
        effective_tokens += 2

    if effective_tokens < 5:
        missing.append("more context than a one-line command")

    if req.asset_type == "grounded-answer":
        if len(tokens) < 4:
            missing.append("what you want the response to do")
        examples.append("Explain AI Gateway for a university CIO in three short paragraphs, focusing on governed AI access for students and faculty.")
    elif req.asset_type == "outbound-email":
        if not req.product:
            missing.append("which product or surface this email is about")
        if not audience and not any(term in lower for term in ("buyer", "lead", "team", "director", "vp", "head")):
            missing.append("who the email is for")
        if not any(term in lower for term in ("ask", "meeting", "demo", "follow-up", "intro", "reach out", "write")):
            missing.append("what the email should try to accomplish")
        examples.append("Write an outbound email to Kim Majerus about AI Compass for AWS training leaders. Goal: ask for a follow-up meeting about governed AI tutoring.")
    elif req.asset_type == "reply-email":
        if not any(term in lower for term in ("thread", "prospect:", "customer:", "email:", "re:", "fwd:", "need:")):
            missing.append("the actual incoming email or thread context")
        examples.append("Thread: Hi Jon, can Vocareum provide ChatGPT access for students, and would next Tuesday work for a follow-up? Need: write the best reply.")
    elif req.asset_type in {"sales-collateral", "one-pager", "sales-deck-brief"}:
        if not req.product:
            missing.append("which product or surface the collateral is for")
        if not audience and not any(term in lower for term in ("buyer", "audience", "architect", "leader", "team", "platform")):
            missing.append("who the collateral is for")
        if req.asset_type == "one-pager":
            examples.append("Build a one-pager for On-the-Fly Labs aimed at AWS solutions architects running customer workshops.")
        elif req.asset_type == "sales-deck-brief":
            examples.append("Build a 6-slide deck for AI Gateway aimed at university CIOs evaluating governed AI access.")
        else:
            if not any(term in lower for term in ("one-pager", "collateral", "overview", "sales", "asset", "build")):
                missing.append("what asset you want built")
            examples.append("Build sales collateral for On-the-Fly Labs aimed at AWS solutions architects running customer workshops.")

    if not missing:
        return None
    return {
        "message": "Brief is too thin to generate a good result.",
        "missing": missing,
        "example": examples[0] if examples else "",
    }


def _build_user_prompt(req: GenerateRequest, correction_instructions: str = "") -> str:
    example = resolve_example(req.asset_type, req.objective)
    example_block = example_prompt_block(example).strip() if example else ""
    format_instructions = _output_format_instructions(req)
    product = _resolved_product(req)
    query_text = req.objective
    if product and product.lower() not in query_text.lower():
        query_text = f"{product}. {query_text}"
    grounding = grounding_block(
        query_text,
        req.asset_type,
        example,
        product=product,
    )
    audience = _resolved_audience(req)
    structured_brief = _structured_brief(req)
    if req.asset_type == "reply-email":
        mode_note = "If the user pasted an email thread, treat it as user-provided context and write only the best reply. Explicitly identify every concrete ask in the thread and answer each one."
    elif req.asset_type == "grounded-answer":
        mode_note = "Answer directly from the grounding. If the request asks for copy, write the requested copy. If support is unclear, leave the claim out."
    else:
        mode_note = "Write directly for the requested workflow."
    if audience and req.asset_type in {"sales-collateral", "one-pager", "sales-deck-brief", "outbound-email"}:
        mode_note += f" Keep the named audience explicit in the output: {audience}. Do not replace it with broader generic categories unless the brief explicitly asks for that."
    if audience and req.asset_type == "one-pager":
        mode_note += f" In `Who Uses This`, the first entry must start with `{audience}`."
    brief_advisory = _brief_needs_more_detail(req)
    if brief_advisory:
        mode_note += " The brief is thin or ambiguous. Do your best to infer the user's intent from the wording they gave you. Do not ask follow-up questions. Use the narrowest plausible interpretation, keep claims conservative, and produce the most useful grounded asset you can."
    example_section = f"\n\n{example_block}" if example_block else ""
    return f"""Create a grounded Vocareum deliverable.

Workflow: {req.asset_type}
Objective / thread / brief:
{req.objective}

Audience: {audience or "Not specified"}
Constraints: {req.extra_constraints or "None"}
Format instructions: {format_instructions}
Structured brief:
{structured_brief or "None"}

Use the grounding below.

{grounding}
{example_section}

{mode_note}
{correction_instructions or ""}
Use only proof, names, providers, tools, and metrics that are explicit in the grounding or in the user-supplied thread. If you use an approved public stat, copy the exact stat string from the grounding instead of paraphrasing it. If a sentence is only partially supported, delete it instead of smoothing it over. If live grounding is unavailable, do not imply the latest live doc was read successfully.
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
        return f"{' '.join(sentences[:midpoint])}\n\n{' '.join(sentences[midpoint:])}"
    return f"{single}\n\nThis response is limited to statements supported by the selected grounding."


def _normalize_product_answer(text: str) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if 2 <= len(paragraphs) <= 4:
        return "\n\n".join(paragraphs)
    if len(paragraphs) > 4:
        return "\n\n".join(paragraphs[:4])
    return _force_two_paragraphs(cleaned)


def _sanitize_proof_sections(text: str) -> str:
    patterns = [
        ("Proof", ["CTA"]),
    ]

    def _sanitize_body(body: str) -> str:
        quote_pattern = re.compile(r'["“](.+?)["”]\s*[—-]\s*([^\n]+)')
        match = quote_pattern.search(body)
        if match:
            attribution = match.group(2).strip().rstrip(".")
            return f"Named public proof: {attribution}. Use paraphrased proof only."
        return body.replace('"', "").replace("“", "").replace("”", "").strip()

    updated = text
    for label, next_labels in patterns:
        next_clause = "|".join(re.escape(item) for item in next_labels)
        pattern = re.compile(
            rf"(?ms)^({re.escape(label)}:?\s*)(.*?)(?=^(?:{next_clause}):?\s*|\Z)"
        )
        updated = pattern.sub(lambda m: f"{m.group(1)}{_sanitize_body(m.group(2).strip())}\n\n", updated)
    return updated.strip()


def _normalize_sales_collateral(text: str) -> str:
    labels = ["Headline", "Subhead", "Core Capabilities", "Best-Fit Buyers", "Proof", "CTA"]
    normalized = text.replace("“", "").replace("”", "").replace('"', "")
    for label in labels:
        normalized = re.sub(
            rf"(?m)^(?:[#>*\-\s]*)?(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*(?!:)",
            f"{label}:",
            normalized,
        )
        normalized = re.sub(
            rf"(?<!\n)({re.escape(label)}:)",
            r"\n\1",
            normalized,
        )
    normalized = re.sub(r"(?m)^(Headline:)", r"\1", normalized.lstrip())
    normalized = re.sub(r"(?m)^([A-Za-z][A-Za-z &-]+:)(\S)", r"\1 \2", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _normalize_approved_stats(text: str) -> str:
    normalized = text
    replacements = [
        (
            re.compile(r"(?:\b(?:over|more than|about|approximately|around)\s+)?2(?:\s*million|\s*m)\+?\s+aws learners\b", re.IGNORECASE),
            "2M+ AWS learners",
        ),
        (
            re.compile(r"(?:\b(?:over|more than|about|approximately|around)\s+)?1(?:\s*million|\s*m)\+?\s+annual unique learners\b", re.IGNORECASE),
            "1M+ annual unique learners",
        ),
        (
            re.compile(r"(?:\b(?:over|more than|about|approximately|around)\s+)?5(?:\s*million|\s*m)\+?\s+total platform learners\b", re.IGNORECASE),
            "5M+ total platform learners",
        ),
        (
            re.compile(
                r"(?:\b(?:over|more than|about|approximately|around)\s+)?7,?000\+?\s+(?:institutions globally|institutions and organizations|institutions|organizations)\b",
                re.IGNORECASE,
            ),
            "7,000+ institutions and organizations",
        ),
    ]
    for pattern, replacement in replacements:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _replace_labeled_section(text: str, label: str, new_body: str) -> str:
    labels = ["Audience", "Headline", "Subhead", "Stat Bar", "Problem", "How It Works", "Who Uses This", "Proof", "Quote", "CTA"]
    label_clause = "|".join(re.escape(item) for item in labels)
    pattern = re.compile(
        rf"(?ms)^({re.escape(label)}:?\s*)(.*?)(?=^(?:{label_clause}):?\s*|\Z)"
    )
    replacement = f"{label}: {new_body.strip()}\n"
    return pattern.sub(replacement, text, count=1)


def _split_packet_dash_entries(value: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for item in _section_items(value):
        match = re.search(r"\s[-:]\s", item)
        if not match:
            entries.append({"value": item.strip(), "label": ""})
            continue
        split_at = match.start()
        entries.append({
            "value": item[:split_at].strip(),
            "label": item[split_at + 3 :].strip(),
        })
    return entries


def _build_one_pager_packet(text: str) -> dict | None:
    sections = _extract_labeled_sections(
        text,
        ["Audience", "Headline", "Subhead", "Stat Bar", "Problem", "How It Works", "Who Uses This", "Proof", "Quote", "CTA"],
    )
    required = ["Headline", "Subhead", "Problem", "How It Works", "Who Uses This", "Proof", "CTA"]
    if any(not sections.get(label) for label in required):
        return None

    return {
        "audience": sections.get("Audience", ""),
        "headline": sections.get("Headline", ""),
        "subhead": sections.get("Subhead", ""),
        "stats": _split_packet_dash_entries(sections.get("Stat Bar", ""))[:4],
        "problem": sections.get("Problem", ""),
        "steps": _section_items(sections.get("How It Works", ""))[:4],
        "audiences": _section_items(sections.get("Who Uses This", ""))[:4],
        "proofs": [
            {"reference": item["value"], "signal": item["label"]}
            for item in _split_packet_dash_entries(sections.get("Proof", ""))[:4]
            if item["value"] and not _none_like(item["value"])
        ],
        "quote": "" if _none_like(sections.get("Quote", "")) else sections.get("Quote", ""),
        "cta": sections.get("CTA", ""),
    }


def _sanitize_one_pager_output(req: GenerateRequest, text: str) -> str:
    sections = _extract_labeled_sections(
        text,
        ["Audience", "Headline", "Subhead", "Stat Bar", "Problem", "How It Works", "Who Uses This", "Proof", "Quote", "CTA"],
    )
    if not sections:
        return text

    updated = text
    audience = _resolved_audience(req)
    audience_entries = [item for item in _section_items(sections.get("Who Uses This", "")) if not _none_like(item)]
    if audience:
        target_tokens = _meaningful_phrase_tokens(audience)
        overlapping = [
            item for item in audience_entries
            if audience.lower() in item.lower() or (_meaningful_phrase_tokens(item) & target_tokens)
        ]
        if overlapping:
            audience_entries = overlapping
        elif sections.get("Who Uses This", ""):
            audience_entries = [audience]
    audience_entries = [
        item for item in audience_entries
        if not _looks_like_product_coined_audience(req, item)
    ]
    if audience_entries:
        updated = _replace_labeled_section(updated, "Who Uses This", " | ".join(audience_entries[:3]))

    proof_entries = [
        item for item in _section_items(sections.get("Proof", ""))
        if not _none_like(item) and not _proof_entry_is_placeholder(item) and not _proof_is_disallowed_for_one_pager(item)
    ]
    updated = _replace_labeled_section(updated, "Proof", " | ".join(proof_entries[:3]) if proof_entries else "None")

    quote_value = sections.get("Quote", "")
    if _none_like(quote_value):
        updated = _replace_labeled_section(updated, "Quote", "None")

    return updated.strip()


def _post_process(req: GenerateRequest, text: str) -> str:
    cleaned = text.replace("“", "").replace("”", "").replace('"', "").strip()
    cleaned = _normalize_approved_stats(cleaned)
    if req.asset_type == "grounded-answer":
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    elif req.asset_type in {"sales-collateral", "one-pager"}:
        cleaned = _sanitize_proof_sections(cleaned)
        if req.asset_type == "one-pager":
            cleaned = _sanitize_one_pager_output(req, cleaned)
        if req.asset_type == "sales-collateral":
            cleaned = _normalize_sales_collateral(cleaned)
    elif req.asset_type == "sales-deck-brief":
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    elif req.asset_type == "outbound-email":
        cleaned = _ensure_outbound_next_step(req, cleaned)
    elif req.asset_type == "reply-email":
        cleaned = _force_two_paragraphs(cleaned) if "Subject:" not in cleaned else cleaned
        cleaned = _ensure_reply_addresses_scheduling(req, cleaned)
    return cleaned


def _extract_scheduling_phrase(text: str) -> str:
    patterns = [
        r"(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))?)",
        r"((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))",
        r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))",
    ]
    lowered = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _ensure_reply_addresses_scheduling(req: GenerateRequest, text: str) -> str:
    objective_lower = req.objective.lower()
    has_schedule_ask = any(term in objective_lower for term in ("meeting", "follow-up", "follow up", "schedule", "calendar", "time"))
    if not has_schedule_ask:
        return text
    if any(term in text.lower() for term in ("let me know what time works", "happy to schedule", "works on your side", "suggest an alternative", "calendar invite")):
        return text

    scheduling_phrase = _extract_scheduling_phrase(req.objective)
    if scheduling_phrase:
        schedule_line = (
            f"If {scheduling_phrase} works for you, I am happy to confirm that time. "
            "If not, feel free to suggest an alternative."
        )
    else:
        schedule_line = "Happy to schedule a follow-up. If you have a preferred time, feel free to suggest it."

    if "Best," in text:
        body, signoff = text.rsplit("Best,", 1)
        return f"{body.strip()}\n\n{schedule_line}\n\nBest,{signoff}"
    return f"{text.strip()}\n\n{schedule_line}"


def _extract_outbound_goal(text: str) -> str:
    match = re.search(r"(?:goal|ask)\s*:\s*([^\n.]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    lowered = text.lower()
    if "follow-up meeting" in lowered:
        return "ask for a follow-up meeting"
    if "schedule a demo" in lowered or "demo" in lowered:
        return "ask for a demo"
    if "working session" in lowered:
        return "ask for a working session"
    return ""


def _ensure_outbound_next_step(req: GenerateRequest, text: str) -> str:
    if any(term in text.lower() for term in ("would you be open", "let me know", "happy to discuss", "follow-up meeting", "schedule a demo", "working session")):
        return text
    goal = _extract_outbound_goal(req.objective)
    if not goal:
        return text
    if "meeting" in goal:
        close_line = "If this is relevant, would you be open to a short follow-up meeting next week?"
    elif "demo" in goal:
        close_line = "If this is relevant, would you be open to a short demo?"
    elif "working session" in goal:
        close_line = "If this is relevant, would you be open to a short working session?"
    else:
        close_line = "If this is relevant, I would be glad to discuss it further."
    if "Best," in text:
        body, signoff = text.rsplit("Best,", 1)
        return f"{body.strip()}\n\n{close_line}\n\nBest,{signoff}"
    return f"{text.strip()}\n\n{close_line}"


def _call_model(req: GenerateRequest, request_id: str, correction_instructions: str = "") -> tuple[str, int]:
    from google import genai
    from google.genai import types

    start = time.perf_counter()
    model = _model_name()
    grounding = load_grounding()
    prompt = _build_user_prompt(req, correction_instructions)
    client = genai.Client(api_key=_require_api_key())
    # Structured collateral needs higher temperature to avoid premature stopping.
    temperature = 0.45 if req.asset_type in {"one-pager", "sales-deck-brief"} else 0.25
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_system_instruction(grounding["truth_bundle"]),
            temperature=temperature,
            max_output_tokens=_max_output_tokens(req),
        ),
    )
    raw_text = (response.text or "").strip()
    if req.asset_type in {"grounded-answer", "sales-collateral", "one-pager", "sales-deck-brief"}:
        text = raw_text
    elif matched_products(req.objective) or (req.product and matched_products(req.product)):
        text = _normalize_product_answer(raw_text)
    else:
        text = _force_two_paragraphs(raw_text)
    text = _post_process(req, text)
    if not text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response.")
    duration_ms = round((time.perf_counter() - start) * 1000)
    log.info(
        "generate_pass request_id=%s asset_type=%s duration_ms=%s output_chars=%s correction=%s",
        request_id,
        req.asset_type,
        duration_ms,
        len(text),
        bool(correction_instructions),
    )
    return text, duration_ms


def _validation_support_text(req: GenerateRequest) -> str:
    example = resolve_example(req.asset_type, req.objective)
    product = _resolved_product(req)
    support = selected_grounding_text(
        req.objective,
        req.asset_type,
        example,
        product=product,
    )
    return "\n\n".join(
        part for part in [support, req.objective, req.extra_constraints, _resolved_audience(req), product] if part.strip()
    )


def _detect_schedule_ask(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ("meeting", "follow-up", "follow up", "schedule", "calendar", "time"))


def _extract_labeled_sections(text: str, labels: list[str]) -> dict[str, str]:
    label_clause = "|".join(re.escape(item) for item in labels)
    sections: dict[str, str] = {}
    for label in labels:
        pattern = re.compile(
            rf"(?ms)^{re.escape(label)}:?\s*(.*?)(?=^(?:{label_clause}):?\s*|\Z)"
        )
        match = pattern.search(text)
        sections[label] = match.group(1).strip() if match else ""
    return sections


ONE_PAGER_PLACEHOLDER_PROOF_PATTERNS = (
    re.compile(r"\bsource docs?\b", re.IGNORECASE),
    re.compile(r"\bproduct catalog\b", re.IGNORECASE),
    re.compile(r"\bapproved catalog\b", re.IGNORECASE),
    re.compile(r"\bworkflow\/category\b", re.IGNORECASE),
    re.compile(r"\bworkflow category\b", re.IGNORECASE),
    re.compile(r"\bgrounding\b", re.IGNORECASE),
    re.compile(r"\blast reviewed\b", re.IGNORECASE),
    re.compile(r"\bversion\b", re.IGNORECASE),
)
ONE_PAGER_AUDIENCE_STOPWORDS = {
    "a", "an", "and", "audience", "audiences", "business", "buyer", "buyers",
    "company", "companies", "context", "department", "departments", "director",
    "directors", "enterprise", "for", "group", "groups", "industry", "leader",
    "leaders", "of", "or", "product", "role", "roles", "target", "team",
    "teams", "the", "title", "titles",
}
PRODUCT_COINED_AUDIENCE_ROLE_WORDS = {
    "admin", "admins", "champion", "champions", "course", "courses", "lead",
    "leads", "leader", "leaders", "manager", "managers", "owner", "owners",
    "team", "teams",
}


def _section_items(section_body: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"\|", section_body or "")
        if item and item.strip()
    ]


def _none_like(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.strip().strip(".,:;()")).lower()
    return normalized in {"none", "n/a", "not available", "not applicable", "no proof", "no quote"}


def _meaningful_phrase_tokens(value: str) -> set[str]:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", normalized)
        if token not in ONE_PAGER_AUDIENCE_STOPWORDS
    }


def _proof_entry_is_placeholder(entry: str) -> bool:
    if _none_like(entry):
        return True
    return any(pattern.search(entry) for pattern in ONE_PAGER_PLACEHOLDER_PROOF_PATTERNS)


WEAK_ONE_PAGER_CTA_PATTERNS = (
    re.compile(r"^\s*learn\s+how\b", re.IGNORECASE),
    re.compile(r"^\s*learn\s+more\b", re.IGNORECASE),
    re.compile(r"^\s*discover\b", re.IGNORECASE),
)


def _one_pager_cta_strength(cta_text: str) -> int:
    cta = cta_text.strip()
    if not cta or cta.lower() == "not available":
        return 2
    if any(pattern.search(cta) for pattern in WEAK_ONE_PAGER_CTA_PATTERNS):
        return 3
    if re.search(r"\b(schedule|demo|review|discuss|evaluate|explore|contact|map|pilot|plan)\b", cta, re.IGNORECASE):
        return 5
    return 4


def _looks_like_product_coined_audience(req: GenerateRequest, entry: str) -> bool:
    lowered_entry = entry.lower()
    if lowered_entry in req.objective.lower():
        return False

    product_tokens = [
        token for token in _meaningful_phrase_tokens(_resolved_product(req))
        if token not in {"vocareum", "platform"}
    ]
    if not product_tokens:
        return False

    entry_tokens = _meaningful_phrase_tokens(entry)
    if not entry_tokens:
        return False

    product_overlap = entry_tokens & set(product_tokens)
    role_overlap = entry_tokens & PRODUCT_COINED_AUDIENCE_ROLE_WORDS
    hyphenated = "-" in entry and bool(product_overlap)
    return bool(product_overlap and role_overlap) or hyphenated


def _proof_is_disallowed_for_one_pager(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in DISALLOWED_ONE_PAGER_PROOF_PATTERNS)


def _resolved_products(req: GenerateRequest) -> list[str]:
    products = matched_products(f"{req.product} {req.objective}")
    if products:
        return products
    resolved = _resolved_product(req)
    return [resolved] if resolved else []


def _one_pager_best_fit_entries(req: GenerateRequest, entries: list[str]) -> list[str]:
    explicit_audience = _resolved_audience(req)
    cleaned = [
        item.strip()
        for item in entries
        if item.strip()
        and not _none_like(item)
        and not _looks_like_product_coined_audience(req, item)
    ]
    if explicit_audience:
        target_tokens = _meaningful_phrase_tokens(explicit_audience)
        anchored = [
            item for item in cleaned
            if explicit_audience.lower() in item.lower() or (_meaningful_phrase_tokens(item) & target_tokens)
        ]
        seeded = [explicit_audience]
        for item in anchored:
            if item.lower() != explicit_audience.lower():
                seeded.append(item)
        cleaned = seeded
        unique: list[str] = []
        seen: set[str] = set()
        for item in cleaned:
            normalized = item.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(item)
        return unique[:3]

    if len(cleaned) < 2:
        for product in _resolved_products(req):
            for item in ONE_PAGER_DEFAULT_BUYERS.get(product, []):
                if item not in cleaned:
                    cleaned.append(item)
                if len(cleaned) >= 3:
                    break
            if len(cleaned) >= 3:
                break

    unique: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        normalized = item.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(item)
    return unique[:3]


def _one_pager_audience_eyebrow(req: GenerateRequest, best_fit: list[str]) -> str:
    explicit_audience = _resolved_audience(req)
    if explicit_audience:
        return f"For {explicit_audience}"
    if best_fit:
        return f"For {best_fit[0]}"
    products = _resolved_products(req)
    if products:
        return f"For teams evaluating {products[0]}"
    return "For teams evaluating Vocareum"


def _proof_library_entry(name: str) -> dict | None:
    for key, value in ONE_PAGER_PROOF_LIBRARY.items():
        if key.lower() == name.lower():
            return value
    return None


def _logo_entry(name: str) -> dict | None:
    for key, value in ONE_PAGER_LOGO_LIBRARY.items():
        if key.lower() == name.lower():
            return value
    return None


def _proof_priority_for_request(req: GenerateRequest, proof_name: str, base_priority: int) -> int:
    score = base_priority
    proof = _proof_library_entry(proof_name)
    if not proof:
        return score
    tags = {item.lower() for item in proof.get("tags", set())}
    products = {item.lower() for item in _resolved_products(req)}
    audience = _resolved_audience(req).lower()
    objective = req.objective.lower()
    if tags & products:
        score += 18
    if any(tag in objective for tag in tags):
        score += 6
    if audience and any(token in audience for token in ("provost", "faculty", "teaching", "learning", "university", "academic")) and "higher education" in tags:
        score += 5
    return score


def _select_one_pager_proof_cards(req: GenerateRequest, proofs: list[dict[str, str]]) -> list[dict]:
    ranked: list[tuple[int, dict]] = []
    used_explicit_proof = False
    for item in proofs:
        reference = item.get("reference", "").strip()
        if not reference or _proof_is_disallowed_for_one_pager(reference):
            continue
        proof = _proof_library_entry(reference)
        if not proof:
            continue
        card = {
            "organization": proof["organization"],
            "use_case": proof["use_case"],
            "what_it_proves": proof["what_it_proves"],
            "source_url": proof["source_url"],
        }
        logo = _logo_entry(reference)
        if logo:
            card["logo"] = logo
        ranked.append((_proof_priority_for_request(req, reference, int(proof.get("priority", 0))), card))
        used_explicit_proof = True

    if not ranked:
        for product in _resolved_products(req):
            for candidate_name, proof in ONE_PAGER_PROOF_LIBRARY.items():
                if _proof_is_disallowed_for_one_pager(candidate_name):
                    continue
                tags = {item.lower() for item in proof.get("tags", set())}
                if product.lower() not in tags:
                    continue
                if candidate_name == "National Research Platform" and "national research platform" not in req.objective.lower():
                    continue
                card = {
                    "organization": proof["organization"],
                    "use_case": proof["use_case"],
                    "what_it_proves": proof["what_it_proves"],
                    "source_url": proof["source_url"],
                    "relation": "Related proof",
                }
                logo = _logo_entry(candidate_name)
                if logo:
                    card["logo"] = logo
                ranked.append((_proof_priority_for_request(req, candidate_name, int(proof.get("priority", 0))), card))

    ranked.sort(key=lambda item: item[0], reverse=True)
    deduped: list[dict] = []
    seen: set[str] = set()
    for _score, card in ranked:
        key = card["organization"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
        if len(deduped) >= 2:
            break
    return deduped


def _one_pager_logo_strip(req: GenerateRequest, proof_cards: list[dict]) -> list[dict]:
    logos: list[dict] = []
    seen: set[str] = set()
    for card in proof_cards:
        logo = card.get("logo")
        if not logo:
            continue
        if logo["name"].lower() in seen:
            continue
        seen.add(logo["name"].lower())
        logos.append(logo)
    return logos[:4]


def _one_pager_footer_quote(req: GenerateRequest, proof_cards: list[dict]) -> dict | None:
    lowered = f"{req.objective} {_resolved_audience(req)} {_resolved_product(req)}".lower()
    learning_signals = {
        "academy", "bootcamp", "course", "courses", "coursera", "enablement",
        "instructor", "learning", "lms", "students", "teaching", "training", "workshop",
    }
    if any(signal in lowered for signal in learning_signals):
        return DEFAULT_ONE_PAGER_QUOTE
    if any((card.get("organization") or "").lower() in {"databricks", "databricks academy"} for card in proof_cards):
        return DEFAULT_ONE_PAGER_QUOTE
    return None


def _one_pager_credibility_bar(req: GenerateRequest, proof_cards: list[dict]) -> list[str]:
    items = [
        "5M+ total platform learners",
        "7,000+ institutions and organizations",
        "SOC 2 Type II, FERPA, GDPR",
        "AWS, Azure, GCP, Databricks",
    ]
    if proof_cards:
        items[0] = "Selected customer and partner proof"
    return items


def _enrich_one_pager_packet(req: GenerateRequest, packet: dict | None) -> dict | None:
    if not packet:
        return None
    best_fit = _one_pager_best_fit_entries(req, list(packet.get("audiences", [])))
    proof_cards = _select_one_pager_proof_cards(req, list(packet.get("proofs", [])))
    packet["audiences"] = best_fit
    packet["proofs"] = [
        item for item in packet.get("proofs", [])
        if item.get("reference") and not _proof_is_disallowed_for_one_pager(item["reference"])
    ]
    packet["audience_eyebrow"] = _one_pager_audience_eyebrow(req, best_fit)
    packet["audience_heading"] = "Best fit"
    packet["problem_heading"] = "Why this matters"
    packet["steps_heading"] = "How Vocareum helps"
    packet["proof_heading"] = "Related proof in market" if proof_cards and not packet["proofs"] else "Why believe this"
    packet["cta_label"] = "Next business step"
    packet["proof_cards"] = proof_cards
    packet["logo_strip"] = _one_pager_logo_strip(req, proof_cards)
    packet["credibility_bar"] = _one_pager_credibility_bar(req, proof_cards)
    packet["footer_quote"] = _one_pager_footer_quote(req, proof_cards)
    packet["render_version"] = "2026-04-30-v3"
    packet["raw_quote"] = packet.get("quote", "")
    packet["quote"] = ""
    return packet


def _one_pager_quality_flags(req: GenerateRequest, output: str) -> dict:
    sections = _extract_labeled_sections(
        output,
        ["Audience", "Headline", "Subhead", "Stat Bar", "Problem", "How It Works", "Who Uses This", "Proof", "Quote", "CTA"],
    )
    proof_entries = [item for item in _section_items(sections.get("Proof", "")) if not _none_like(item)]
    placeholder_proof = any(_proof_entry_is_placeholder(item) for item in proof_entries)
    has_named_proof = bool(proof_entries) and not placeholder_proof
    banned_proof = any(_proof_is_disallowed_for_one_pager(item) for item in proof_entries)
    weak_named_proof = bool(proof_entries) and all(
        not any(reference.lower() in item.lower() for reference in HIGH_SIGNAL_ONE_PAGER_PROOFS)
        for item in proof_entries
    )

    named_audience = _resolved_audience(req)
    audience_entries = [item for item in _section_items(sections.get("Who Uses This", "")) if not _none_like(item)]
    audience_drift = False
    generic_audience = any(
        _meaningful_phrase_tokens(item) <= {"learners", "researchers", "technical"}
        or item.lower() in {"learners", "researchers", "technical teams", "business teams", "healthcare teams"}
        for item in audience_entries
    )
    if named_audience and audience_entries:
        target_tokens = _meaningful_phrase_tokens(named_audience)
        if target_tokens:
            overlapping = [
                item for item in audience_entries
                if _meaningful_phrase_tokens(item) & target_tokens
            ]
            audience_drift = bool(overlapping) and len(overlapping) < len(audience_entries)

    return {
        "sections": sections,
        "has_named_proof": has_named_proof,
        "placeholder_proof": placeholder_proof,
        "audience_drift": audience_drift,
        "generic_audience": generic_audience,
        "banned_proof": banned_proof,
        "weak_named_proof": weak_named_proof,
    }


def _auto_quality_report(req: GenerateRequest, output: str, support_text: str, truth_bundle: dict) -> dict:
    validation = validate_output(
        asset_type=req.asset_type,
        text=output,
        support_text=support_text,
        truth_bundle=truth_bundle,
        objective_text=req.objective,
    )
    scores = []
    blockers: list[str] = []
    strengths: list[str] = []
    improvements: list[str] = []

    grounding_score = 5 if validation.ok else max(1, 5 - min(4, len(validation.issues)))
    if validation.ok:
        strengths.append("No deterministic grounding violations detected.")
    else:
        blockers.extend(issue.detail for issue in validation.issues[:4])
        improvements.append("Tighten unsupported claims and proof references.")
    scores.append({"id": "grounding", "label": "Grounding safety", "score": grounding_score})
    one_pager_flags = _one_pager_quality_flags(req, output) if req.asset_type == "one-pager" else None
    if one_pager_flags and one_pager_flags["placeholder_proof"]:
        grounding_score = min(grounding_score, 3)
        scores[-1]["score"] = grounding_score
        blockers.append("One-pager uses placeholder proof instead of approved named public proof.")
        improvements.append("Replace placeholder proof with approved named proof, or use `Proof: None`.")
    if one_pager_flags and one_pager_flags["banned_proof"]:
        grounding_score = 1
        scores[-1]["score"] = grounding_score
        blockers.append("One-pager uses a banned proof source.")
        improvements.append("Remove banned proof sources such as NAIRR from the one-pager.")

    if req.asset_type == "grounded-answer":
        specificity_score, _signals = _specificity_score(req, output)
        if specificity_score >= 4:
            strengths.append("Response is specific to the prompt.")
        else:
            improvements.append("Make the response more specific to the requested ask.")
        scores.append({"id": "specificity", "label": "Specificity", "score": specificity_score})
        overall = round(sum(item["score"] for item in scores) / len(scores), 1)
        status = "strong" if overall >= 4.3 else "usable" if overall >= 3.3 else "needs-work"
        return {
            "overall_score": overall,
            "status": status,
            "scores": scores,
            "blockers": blockers[:4],
            "strengths": strengths[:4],
            "improvements": improvements[:4],
        }

    has_subject = output.strip().startswith("Subject:")
    is_collateral = req.asset_type in {"sales-collateral", "one-pager", "sales-deck-brief"}
    workflow_score = 5 if has_subject or is_collateral else 2
    if req.asset_type == "one-pager":
        required_sections = ["Headline", "Subhead", "Stat Bar", "Problem", "How It Works", "Who Uses This", "Proof", "CTA"]
        sections = _extract_labeled_sections(output, required_sections)
        present = sum(1 for label in required_sections if sections.get(label))
        workflow_score = max(1, min(5, round(present * 5 / len(required_sections))))
        if present == len(required_sections):
            strengths.append("One-pager structure is complete.")
        else:
            improvements.append("Complete all required one-pager sections.")
        if one_pager_flags and one_pager_flags["placeholder_proof"]:
            workflow_score = min(workflow_score, 3)
            strengths = [item for item in strengths if item != "One-pager structure is complete."]
        if one_pager_flags and one_pager_flags["generic_audience"]:
            workflow_score = min(workflow_score, 3)
    elif req.asset_type == "sales-deck-brief":
        slide_count = len(re.findall(r"(?m)^Slide\s+\d+:", output))
        workflow_score = 5 if slide_count == 6 else max(1, min(5, slide_count))
        if slide_count == 6:
            strengths.append("Deck has all 6 slides.")
        else:
            improvements.append(f"Expected 6 slides, found {slide_count}.")
    elif req.asset_type == "sales-collateral":
        required_labels = ["Headline:", "Subhead:", "Core Capabilities:", "Best-Fit Buyers:", "Proof:", "CTA:"]
        present = sum(1 for label in required_labels if label in output)
        workflow_score = max(1, min(5, present))
        if present == len(required_labels):
            strengths.append("Collateral structure is complete.")
        else:
            improvements.append("Complete all required collateral sections.")
    else:
        if has_subject:
            strengths.append("Email format is send-ready.")
        else:
            improvements.append("Return a full send-ready email with subject line.")
    scores.append({"id": "workflow", "label": "Workflow fit", "score": workflow_score})

    specificity_score, _signals = _specificity_score(req, output)
    if one_pager_flags and one_pager_flags["audience_drift"]:
        specificity_score = max(1, specificity_score - 2)
    if one_pager_flags and one_pager_flags["generic_audience"]:
        specificity_score = max(1, specificity_score - 2)
    if specificity_score >= 4:
        strengths.append("Output is specific to the requested product or audience.")
    else:
        improvements.append("Make the output more specific to the named person, audience, or product.")
    if one_pager_flags and one_pager_flags["audience_drift"]:
        improvements.append("Keep `Who Uses This` anchored to the named audience instead of broadening into generic sectors.")
    if one_pager_flags and one_pager_flags["generic_audience"]:
        improvements.append("Replace generic audience labels with specific buyers or operators who would actually use this asset.")
    scores.append({"id": "specificity", "label": "Specificity", "score": specificity_score})

    actionability_score = 3
    if req.asset_type == "sales-collateral":
        actionability_score = 5 if "CTA:" in output else 2
    elif req.asset_type == "one-pager":
        cta_match = re.search(r"(?ms)^CTA:\s*(.+)$", output)
        cta_text = cta_match.group(1).strip() if cta_match else ""
        actionability_score = _one_pager_cta_strength(cta_text)
    else:
        has_next_step = any(term in output.lower() for term in ("meeting", "follow-up", "calendar", "demo", "let me know", "suggest an alternative"))
        if _detect_schedule_ask(req.objective):
            actionability_score = 5 if has_next_step else 2
        else:
            actionability_score = 4 if has_next_step else 3
    if actionability_score >= 4:
        strengths.append("Output includes a concrete next step.")
    else:
        improvements.append("Add a clearer next step or call to action.")
    scores.append({"id": "actionability", "label": "Actionability", "score": actionability_score})

    completeness_score = 4
    if req.asset_type == "one-pager":
        completeness_score = 5
        if one_pager_flags and one_pager_flags["placeholder_proof"]:
            completeness_score = 2
        elif one_pager_flags and one_pager_flags["banned_proof"]:
            completeness_score = 1
        elif one_pager_flags and not one_pager_flags["has_named_proof"]:
            completeness_score = 2
            improvements.append("Use approved named public proof when available. If none exists, explicitly mark `Proof: None`.")
        elif one_pager_flags and one_pager_flags["weak_named_proof"]:
            completeness_score = min(completeness_score, 3)
            improvements.append("Use proof that is understandable to a cold reader, or rely on scale/compliance credibility instead of weak named proof.")
    elif req.asset_type == "reply-email":
        asks = 1
        if _detect_schedule_ask(req.objective):
            asks += 1
        answered_schedule = not _detect_schedule_ask(req.objective) or any(
            term in output.lower() for term in ("works for you", "calendar", "suggest an alternative", "confirm that time")
        )
        completeness_score = 5 if answered_schedule and asks >= 2 else 3 if answered_schedule else 1
        if not answered_schedule:
            blockers.append("Reply does not address the scheduling ask from the thread.")
    scores.append({"id": "completeness", "label": "Completeness", "score": completeness_score})

    overall = round(sum(item["score"] for item in scores) / len(scores), 1)
    if req.asset_type == "one-pager" and specificity_score <= 2:
        blockers.append("One-pager is not specific enough to the named buyer or workflow.")
        overall = min(overall, 3.0)
    if req.asset_type == "one-pager" and one_pager_flags and one_pager_flags["weak_named_proof"] and specificity_score <= 3:
        overall = min(overall, 2.8)
    status = "strong" if overall >= 4.3 else "usable" if overall >= 3.3 else "needs-work"
    if req.asset_type == "one-pager" and specificity_score <= 2:
        status = "needs-work"
    return {
        "overall_score": overall,
        "status": status,
        "scores": scores,
        "blockers": blockers[:4],
        "strengths": strengths[:4],
        "improvements": improvements[:4],
    }


def _one_pager_missing_sections(text: str) -> list[str]:
    required = ["Headline", "Subhead", "Stat Bar", "Problem", "How It Works", "Who Uses This", "Proof", "CTA"]
    sections = _extract_labeled_sections(text, ["Audience", *required])
    return [label for label in required if not sections.get(label)]


def _critic_review_and_select(
    req: GenerateRequest,
    current_text: str,
    support_text: str,
    truth_bundle: dict,
    request_id: str,
) -> tuple[str, int]:
    if req.asset_type != "one-pager":
        return current_text, 0

    base_report = _auto_quality_report(req, current_text, support_text, truth_bundle)
    audience = _resolved_audience(req)
    product = _resolved_product(req)
    critic_notes: list[str] = []
    if audience:
        critic_notes.append(f"Keep `{audience}` explicit as the named audience.")
    if product:
        critic_notes.append(f"Keep `{product}` explicit as the named product surface.")
    critic_notes.append("Rewrite for a cold reader who knows nothing about Vocareum. The draft should answer what this is, who it is for, why to believe it, and what to do next.")
    critic_notes.append("If there is no approved named public proof, write `Proof: None` instead of using source metadata or placeholders.")
    critic_notes.append("Never use NAIRR references in the one-pager.")
    critic_notes.append("Do not invent extra sectors, departments, or buyer groups when the brief only names one audience.")
    critic_notes.append("Do not coin buyer labels from product names, internal jargon, or hyphenated product-role mashups.")
    critic_notes.append("Do not use generic audience labels like learners, researchers, business teams, or technical teams.")
    critic_notes.append("If you use named proof, make the signal understandable to a cold reader.")
    missing_sections = _one_pager_missing_sections(current_text)
    if missing_sections:
        critic_notes.append("Fill every missing or empty labeled section: " + ", ".join(missing_sections) + ".")
    for item in base_report.get("blockers", [])[:4]:
        critic_notes.append(item)
    for item in base_report.get("improvements", [])[:4]:
        critic_notes.append(item)
    if not critic_notes:
        critic_notes.append("Tighten clarity, specificity, and buyer fit without changing grounded facts.")

    correction = (
        "You are the marketing-and-message critic reviewing a grounded one-pager draft before it is shown to the user.\n"
        "Return a revised one-pager only. Keep the same labeled section structure. Do not explain your edits.\n"
        "Preserve grounded facts, approved stats, and approved proof. Do not invent proof.\n"
        "Make the copy more specific, sharper, and more buyer-aware.\n"
        "Critic notes:\n"
        + "\n".join(f"- {note}" for note in critic_notes)
        + "\n\nCurrent draft:\n"
        + current_text
    )

    candidate_text, critic_ms = _call_model(req, request_id, correction)
    candidate_validation = validate_output(
        asset_type=req.asset_type,
        text=candidate_text,
        support_text=support_text,
        truth_bundle=truth_bundle,
        objective_text=req.objective,
    )
    if not candidate_validation.ok:
        return current_text, critic_ms

    candidate_report = _auto_quality_report(req, candidate_text, support_text, truth_bundle)
    if candidate_report.get("overall_score", 0) >= base_report.get("overall_score", 0):
        return candidate_text, critic_ms
    return current_text, critic_ms


def _prefer_candidate(
    req: GenerateRequest,
    support_text: str,
    truth_bundle: dict,
    objective_text: str,
    candidates: list[tuple[str, object]],
) -> str:
    ranked: list[tuple[int, float, int, str]] = []
    for index, (text, validation) in enumerate(candidates):
        report = _auto_quality_report(req, text, support_text, truth_bundle)
        issue_count = len(validation.issues)
        score = float(report.get("overall_score", 0))
        ranked.append((issue_count, -score, index, text))
    ranked.sort()
    return ranked[0][3]


def _generate_text(req: GenerateRequest, request_id: str) -> tuple[str, int]:
    grounding = load_grounding()
    support_text = _validation_support_text(req)
    truth_bundle = grounding["truth_bundle"]

    draft, duration_ms = _call_model(req, request_id)

    # For one-pagers, if the model stopped early (missing sections), ask it
    # to continue from the partial output rather than regenerating from scratch.
    if req.asset_type == "one-pager":
        missing = _one_pager_missing_sections(draft)
        if missing:
            continuation = (
                f"Here is the partial one-pager so far:\n\n{draft}\n\n"
                f"Continue from where the output stopped. Write ONLY the remaining sections: {', '.join(missing)}. "
                "Use the same style. Keep each section concise."
            )
            tail, extra_ms = _call_model(req, request_id, continuation)
            duration_ms += extra_ms
            # Append the continuation to the draft
            draft = draft.rstrip() + "\n\n" + tail.lstrip()

    first_validation = validate_output(
        asset_type=req.asset_type,
        text=draft,
        support_text=support_text,
        truth_bundle=truth_bundle,
        objective_text=req.objective,
    )
    if first_validation.ok:
        reviewed_text, review_ms = _critic_review_and_select(
            req,
            draft,
            support_text,
            truth_bundle,
            request_id,
        )
        return reviewed_text, duration_ms + review_ms

    fix_lines = "\n".join(f"- {issue.code}: {issue.detail} | {issue.snippet}" for issue in first_validation.issues[:8])
    correction = (
        "The first draft failed deterministic validation. Rewrite it so every claim is supported.\n"
        "Replace paraphrased public stats with the exact grounded stat strings. Delete unsupported bridge sentences instead of rewording them.\n"
        "Fix these exact issues and keep the same workflow:\n"
        f"{fix_lines}"
    )
    revised, second_duration_ms = _call_model(req, request_id, correction)
    second_validation = validate_output(
        asset_type=req.asset_type,
        text=revised,
        support_text=support_text,
        truth_bundle=truth_bundle,
        objective_text=req.objective,
    )
    if second_validation.ok:
        reviewed_text, review_ms = _critic_review_and_select(
            req,
            revised,
            support_text,
            truth_bundle,
            request_id,
        )
        return reviewed_text, duration_ms + second_duration_ms + review_ms

    log.warning(
        "validation_failed request_id=%s asset_type=%s issues=%s",
        request_id,
        req.asset_type,
        [issue.code for issue in second_validation.issues],
    )
    best_effort = _prefer_candidate(
        req,
        support_text,
        truth_bundle,
        req.objective,
        [
            (draft, first_validation),
            (revised, second_validation),
        ],
    )
    return best_effort, duration_ms + second_duration_ms


def _improve_text(
    req: GenerateRequest,
    current_output: str,
    rating: int,
    notes: str,
    request_id: str,
) -> tuple[str, int]:
    grounding = load_grounding()
    support_text = _validation_support_text(req)
    truth_bundle = grounding["truth_bundle"]
    quality_report = _auto_quality_report(req, current_output, support_text, grounding["truth_bundle"])
    issues = "\n".join(f"- {item}" for item in quality_report.get("blockers", [])[:4])
    suggestions = "\n".join(f"- {item}" for item in quality_report.get("improvements", [])[:4])
    correction = f"""Improve the existing draft without changing the underlying grounded facts.

Current draft:
{current_output}

User rating: {rating}/5
User feedback:
{notes or 'No extra user feedback provided.'}

Auto-evaluation blockers:
{issues or '- none'}

Auto-evaluation improvements:
{suggestions or '- make the output sharper and more specific'}

Produce a better version for the same workflow. Keep only grounded facts. Be more specific, more usable, and cleaner than the current draft."""
    revised, duration_ms = _call_model(req, request_id, correction)
    validation = validate_output(
        asset_type=req.asset_type,
        text=revised,
        support_text=support_text,
        truth_bundle=truth_bundle,
        objective_text=req.objective,
    )
    if not validation.ok:
        current_validation = validate_output(
            asset_type=req.asset_type,
            text=current_output,
            support_text=support_text,
            truth_bundle=truth_bundle,
            objective_text=req.objective,
        )
        best_effort = _prefer_candidate(
            req,
            support_text,
            truth_bundle,
            req.objective,
            [
                (current_output, current_validation),
                (revised, validation),
            ],
        )
        return best_effort, duration_ms
    return revised, duration_ms


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
        "source_doc_url": source.get("doc_url"),
        "source_modified_time": source.get("modified_time"),
        "source_version": source.get("version"),
        "source_checked_at": source.get("checked_at"),
        "grounding_mode": grounding.get("mode", "live"),
        "grounding_warnings": grounding.get("warnings", []),
    }


@app.get("/api/meta")
def meta(force: bool = False) -> dict:
    data = load_grounding(force=force)
    return _meta_payload(data)


@app.post("/api/source/refresh")
def source_refresh() -> dict:
    data = load_grounding(force=True)
    return _meta_payload(data)


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
    content_packet = _enrich_one_pager_packet(req, _build_one_pager_packet(output)) if req.asset_type == "one-pager" else None
    quality_report = _auto_quality_report(
        req,
        output,
        _validation_support_text(req),
        data["truth_bundle"],
    )
    return GenerateResponse(
        output=output,
        model=_model_name(),
        **_source_response_fields(data),
        grounding_mode=data.get("mode", "live"),
        grounding_warnings=data.get("warnings", []),
        request_id=request_id,
        duration_ms=duration_ms,
        rendered_html=rendered["html"] if rendered else None,
        rendered_kind=rendered["kind"] if rendered else None,
        rendered_title=rendered["title"] if rendered else None,
        content_packet=content_packet,
        quality_report=quality_report,
    )


@app.post("/api/improve", response_model=GenerateResponse)
def improve(req: ImproveRequest) -> GenerateResponse:
    data = load_grounding()
    request_id = uuid.uuid4().hex[:12]
    try:
        output, duration_ms = _improve_text(
            req.request,
            req.current_output,
            req.rating,
            req.notes,
            request_id,
        )
    except Exception:
        log.exception("improve_failed request_id=%s model=%s", request_id, _model_name())
        raise
    rendered = render_collateral(req.request.asset_type, output)
    content_packet = _enrich_one_pager_packet(req.request, _build_one_pager_packet(output)) if req.request.asset_type == "one-pager" else None
    quality_report = _auto_quality_report(
        req.request,
        output,
        _validation_support_text(req.request),
        data["truth_bundle"],
    )
    return GenerateResponse(
        output=output,
        model=_model_name(),
        **_source_response_fields(data),
        grounding_mode=data.get("mode", "live"),
        grounding_warnings=data.get("warnings", []),
        request_id=request_id,
        duration_ms=duration_ms,
        rendered_html=rendered["html"] if rendered else None,
        rendered_kind=rendered["kind"] if rendered else None,
        rendered_title=rendered["title"] if rendered else None,
        content_packet=content_packet,
        quality_report=quality_report,
    )
