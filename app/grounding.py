from __future__ import annotations

import io
import json
import os
import re
import time
from pathlib import Path

import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
GROUNDING_FILE = DATA_DIR / "grounding_snapshot.json"
CATALOG_FILE = DATA_DIR / "product_catalog_v1.1.md"

VOC_PRODUCT_CATALOG_DOC_ID = os.environ.get(
    "VOC_PRODUCT_CATALOG_DOC_ID",
    "1GTyQXMbz2l4ERcx1EwVyewr4Mp2vWjtyamNx0zd_rOc",
)
VOC_APPROVED_EMAIL_DOC_ID = os.environ.get(
    "VOC_APPROVED_EMAIL_DOC_ID",
    "1qGnSdEySKBFx2hbj-C8KmOxUq4vuzfiGXkL11AtDENA",
)
VOC_EXAMPLE_COLLATERAL_FOLDER_ID = os.environ.get(
    "VOC_EXAMPLE_COLLATERAL_FOLDER_ID",
    "1iyBguF5zprS4ykUaiRWiJIHA6Nd3Ss-j",
)
LIVE_GROUNDING_TTL_SECONDS = int(os.environ.get("LIVE_GROUNDING_TTL_SECONDS", "120"))
SOURCE_TITLE = "Vocareum Product & Feature Catalog"
APPROVED_EMAIL_TITLE = "Vocareum Approved Email Material"

DRIVE_READONLY_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
MIME_DOC = "application/vnd.google-apps.document"
MIME_PRESENTATION = "application/vnd.google-apps.presentation"
MIME_SHORTCUT = "application/vnd.google-apps.shortcut"
MIME_PDF = "application/pdf"

PRODUCT_ALIASES: dict[str, tuple[str, ...]] = {
    "AI Notebook": ("ai notebook", "vocareum notebook", "notebook"),
    "Cloud Labs": ("cloud labs", "cloud lab"),
    "AI Gateway": ("ai gateway", "gateway"),
    "Developer Workspaces": (
        "developer workspaces",
        "developer workspace",
        "vs code",
        "jupyterlab",
        "rstudio",
        "terminal workspace",
        "linux desktop",
        "windows vdi",
    ),
    "Virtual Desktop": ("virtual desktop", "virtual desktops"),
    "AI Compass": ("ai compass", "compass"),
    "Agentic AI Labs": ("agentic ai labs", "agentic labs", "agentic lab"),
    "On-the-Fly Labs": ("on-the-fly labs", "on the fly labs", "on-the-fly lab"),
    "Simulations": ("simulations", "simulation"),
    "Databases": ("databases", "database"),
    "GPU & CPU Compute": ("gpu", "cpu compute", "gpu compute", "hpc"),
    "Cyber Ranges": ("cyber ranges", "cyber range"),
    "Platform Enablement Labs": ("platform enablement labs", "platform enablement lab"),
}

PRODUCT_SECTION_TITLES = [
    "AI Notebook",
    "Cloud Labs",
    "AI Gateway",
    "Developer Workspaces",
    "Virtual Desktop",
    "AI Compass",
    "Agentic AI Labs",
    "On-the-Fly Labs",
    "Simulations",
    "Databases",
    "GPU & CPU Compute",
    "Cyber Ranges",
    "Platform Enablement Labs",
    "All Features",
    "All Resources",
    "All Teaching & Learning Tools",
    "All Admin Tools",
]

EMAIL_SECTION_BY_PATTERN = {
    "governed-model-access": "AI Gateway / Governed Model Access",
    "short-demo-follow-up": "Short Strategic Add-On After Demo",
    "capability-boundary": "Supported Today / Capability-Boundary Reply",
    "partner-case-study": "Partner Case-Study Framing",
    "scheduling-follow-up": "Scheduling / Positive Follow-Up Reply",
    "post-event-follow-up": "Strategic Post-Event Follow-Up",
}

COLLATERAL_FILES_BY_PATTERN = {
    "aws-cosell-one-pager": [
        "Vocareum_On_the_Fly_Labs_AWS_Co_Sell.pdf",
        "Vocareum Overview Q1 2026",
    ],
    "method-one-pager": ["Learning Flow Method One-Pager"],
    "product-overview": ["Vocareum Overview Q1 2026"],
    "sales-collateral": ["Vocareum Sales Collateral"],
}

STYLE_PALETTE = {
    "slate": "#2e3a41",
    "white": "#ffffff",
    "black": "#000000",
    "steel": "#445664",
    "powder": "#c1d3dd",
    "light_gray": "#efefef",
    "coral": "#ff7f50",
}

DEFAULT_PUBLIC_STATS = [
    "Since 2012",
    "50M+ learner labs launched",
    "5M+ learners served",
    "7,000+ institutions and organizations",
]
CONTEXTUAL_STATS = [
    "1M+ annual unique learners",
    "2M+ AWS learners",
]
AUDIENCE_DOORS = [
    "Colleges & Universities",
    "Learning Platforms & EdTech",
    "Certification & Credentialing",
    "Technology Companies & Platforms",
    "Global Services & Consulting",
    "Online Universities & Scale Providers",
]
PROOF_POSTURES = [
    {
        "id": "strict-default",
        "label": "Strict default public proof",
        "description": "Use only the default public stats surface unless a source-specific proof anchor is explicitly needed.",
    },
    {
        "id": "contextual-allowed",
        "label": "Allow contextual proof",
        "description": "Allow contextual approved stats like 1M+ annual unique learners or 2M+ AWS learners only when the request and support materials clearly justify them.",
    },
    {
        "id": "named-proof-priority",
        "label": "Named proof priority",
        "description": "Prefer named public proof and qualitative support over broad scale anchors.",
    },
]

_BUNDLE_CACHE: dict[str, object] = {"bundle": None, "loaded_at": 0.0}


def _drive_service():
    try:
        from core.google_auth import DRIVE_READONLY_TOKEN_FILE, get_google_credentials

        creds = get_google_credentials(
            DRIVE_READONLY_SCOPES,
            token_file=DRIVE_READONLY_TOKEN_FILE,
        )
    except Exception:
        creds, _project = google.auth.default(scopes=DRIVE_READONLY_SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _download_bytes(request) -> bytes:
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    return buf.getvalue()


def _export_doc_text(service, file_id: str) -> str:
    payload = service.files().export(fileId=file_id, mimeType="text/plain").execute()
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    return str(payload)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n\n".join(part for part in parts if part.strip())


def _resolve_shortcut(service, item: dict) -> dict:
    if item.get("mimeType") != MIME_SHORTCUT:
        return item
    details = service.files().get(
        fileId=item["id"],
        fields="shortcutDetails(targetId,targetMimeType)",
        supportsAllDrives=True,
    ).execute()
    shortcut = details.get("shortcutDetails") or {}
    return {
        "id": shortcut.get("targetId", item["id"]),
        "name": item.get("name", ""),
        "mimeType": shortcut.get("targetMimeType", item.get("mimeType", "")),
    }


def _read_drive_item_text(service, item: dict) -> str:
    resolved = _resolve_shortcut(service, item)
    file_id = resolved["id"]
    mime = resolved.get("mimeType", "")
    if mime == MIME_DOC:
        return _export_doc_text(service, file_id)
    if mime == MIME_PRESENTATION:
        pdf_bytes = service.files().export(fileId=file_id, mimeType="application/pdf").execute()
        if isinstance(pdf_bytes, str):
            pdf_bytes = pdf_bytes.encode("utf-8")
        return _extract_pdf_text(pdf_bytes)
    if mime == MIME_PDF:
        request = service.files().get_media(fileId=file_id)
        return _extract_pdf_text(_download_bytes(request))

    request = service.files().get_media(fileId=file_id)
    payload = _download_bytes(request)
    return payload.decode("utf-8", errors="replace")


def _strip_markdown_decoration(line: str) -> str:
    return re.sub(r"[*#`_]+", "", line).strip()


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_markdown_decoration(text)).strip().lower()


def _parse_named_sections(text: str, titles: list[str]) -> tuple[str, dict[str, str]]:
    lines = text.splitlines()
    normalized_titles = {_normalize_title(title): title for title in titles}
    starts: list[tuple[str, int]] = []
    for idx, raw_line in enumerate(lines):
        normalized = _normalize_title(raw_line)
        if normalized in normalized_titles:
            starts.append((normalized_titles[normalized], idx))

    sections: dict[str, str] = {}
    if not starts:
        return text.strip(), sections

    first_start = starts[0][1]
    front_matter = "\n".join(lines[:first_start]).strip()
    for index, (title, start_line) in enumerate(starts):
        end_line = starts[index + 1][1] if index + 1 < len(starts) else len(lines)
        section = "\n".join(lines[start_line:end_line]).strip()
        if section:
            sections[title] = section
    return front_matter, sections


def _parse_last_reviewed(text: str) -> str:
    match = re.search(r"Last reviewed\s*\|?\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\b(202\d-\d{2}-\d{2})\b", text)
    if match:
        return match.group(1)
    return "Unknown"


def _parse_title(text: str) -> str:
    match = re.search(r"Vocareum Product\s*&\s*Feature Catalog", text, re.IGNORECASE)
    if match:
        return SOURCE_TITLE
    return SOURCE_TITLE


def _extract_relevant_lines(text: str, query: str, max_lines: int = 24) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    terms = {term for term in re.findall(r"[a-z0-9][a-z0-9+&.-]{2,}", query.lower())}
    if not terms:
        return "\n".join(lines[:max_lines])
    scored: list[tuple[int, str]] = []
    for line in lines:
        lowered = line.lower()
        score = sum(1 for term in terms if term in lowered)
        if score:
            scored.append((score, line))
    if not scored:
        return "\n".join(lines[:max_lines])
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    selected = [line for _score, line in scored[:max_lines]]
    return "\n".join(selected)


def _collateral_matches_query(
    name: str,
    text: str,
    query: str,
    product_hint: str,
    audience_hint: str,
    example_id: str,
) -> int:
    haystack = f"{name}\n{text[:12000]}".lower()
    query_terms = re.findall(r"[a-z0-9][a-z0-9+&.-]{2,}", query.lower())
    score = sum(3 for term in query_terms if term in haystack)
    if product_hint and product_hint.lower() in haystack:
        score += 15
    if audience_hint and audience_hint.lower() in haystack:
        score += 10
    for curated_name in COLLATERAL_FILES_BY_PATTERN.get(example_id, []):
        if curated_name.lower() == name.lower():
            score += 20
    return score


def _fallback_bundle() -> dict:
    try:
        snapshot = json.loads(GROUNDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        snapshot = {
            "source": {
                "title": SOURCE_TITLE,
                "last_reviewed": "Unknown",
                "doc_url": f"https://docs.google.com/document/d/{VOC_PRODUCT_CATALOG_DOC_ID}/edit",
            },
            "style_palette": STYLE_PALETTE,
        }

    catalog_text = CATALOG_FILE.read_text(encoding="utf-8") if CATALOG_FILE.exists() else ""
    catalog_front_matter, catalog_sections = _parse_named_sections(catalog_text, PRODUCT_SECTION_TITLES)
    return {
        "source": snapshot["source"],
        "mode": "fallback",
        "warnings": ["Live Google Drive grounding unavailable. Using local fallback snapshot."],
        "catalog_front_matter": catalog_front_matter,
        "catalog_sections": catalog_sections,
        "email_sections": {},
        "collateral_examples": {},
        "default_public_stats": DEFAULT_PUBLIC_STATS,
        "contextual_stats": CONTEXTUAL_STATS,
        "audience_doors": AUDIENCE_DOORS,
        "proof_postures": PROOF_POSTURES,
        "style_palette": snapshot.get("style_palette", STYLE_PALETTE),
    }


def _load_live_bundle() -> dict:
    service = _drive_service()

    catalog_text = _export_doc_text(service, VOC_PRODUCT_CATALOG_DOC_ID)
    catalog_front_matter, catalog_sections = _parse_named_sections(catalog_text, PRODUCT_SECTION_TITLES)

    email_doc_text = _export_doc_text(service, VOC_APPROVED_EMAIL_DOC_ID)
    email_titles = list(EMAIL_SECTION_BY_PATTERN.values())
    _email_front_matter, email_sections = _parse_named_sections(email_doc_text, email_titles)

    folder_listing = service.files().list(
        q=f"'{VOC_EXAMPLE_COLLATERAL_FOLDER_ID}' in parents and trashed = false",
        pageSize=100,
        fields="files(id,name,mimeType)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    collateral_examples: dict[str, dict[str, str]] = {}
    for item in folder_listing.get("files", []):
        try:
            collateral_examples[item["name"]] = {
                "name": item["name"],
                "text": _read_drive_item_text(service, item),
            }
        except Exception:
            continue

    return {
        "source": {
            "title": _parse_title(catalog_text),
            "last_reviewed": _parse_last_reviewed(catalog_text),
            "doc_url": f"https://docs.google.com/document/d/{VOC_PRODUCT_CATALOG_DOC_ID}/edit",
        },
        "mode": "live",
        "warnings": [],
        "catalog_front_matter": catalog_front_matter,
        "catalog_sections": catalog_sections,
        "email_sections": email_sections,
        "collateral_examples": collateral_examples,
        "default_public_stats": DEFAULT_PUBLIC_STATS,
        "contextual_stats": CONTEXTUAL_STATS,
        "audience_doors": AUDIENCE_DOORS,
        "proof_postures": PROOF_POSTURES,
        "style_palette": STYLE_PALETTE,
    }


def load_grounding() -> dict:
    now = time.time()
    bundle = _BUNDLE_CACHE.get("bundle")
    loaded_at = float(_BUNDLE_CACHE.get("loaded_at") or 0.0)
    if bundle and now - loaded_at < LIVE_GROUNDING_TTL_SECONDS:
        return bundle

    try:
        fresh_bundle = _load_live_bundle()
    except Exception as exc:
        fresh_bundle = _fallback_bundle()
        warnings = list(fresh_bundle.get("warnings", []))
        warnings.append(f"Live grounding error: {exc.__class__.__name__}")
        fresh_bundle["warnings"] = warnings

    _BUNDLE_CACHE["bundle"] = fresh_bundle
    _BUNDLE_CACHE["loaded_at"] = now
    return fresh_bundle


def matched_products(user_text: str) -> list[str]:
    lowered = user_text.lower()
    found: list[str] = []
    for product, aliases in PRODUCT_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            found.append(product)
    return found


def product_grounding_block(user_text: str) -> str:
    matches = matched_products(user_text)
    if not matches:
        return ""
    sections = load_grounding()["catalog_sections"]
    blocks: list[str] = []
    for product in matches[:4]:
        section = sections.get(product, "").strip()
        if section:
            blocks.append(section)
    return "\n\n---\n\n".join(blocks)


def _email_example_block(example_id: str, bundle: dict) -> str:
    section_title = EMAIL_SECTION_BY_PATTERN.get(example_id, "")
    if not section_title:
        return ""
    section = bundle["email_sections"].get(section_title, "").strip()
    if not section:
        return ""
    return f"{APPROVED_EMAIL_TITLE} example:\nSource: {section_title}\n\n{section}"


def _collateral_example_block(
    example_id: str,
    bundle: dict,
    query: str,
    product_hint: str,
    audience_hint: str,
) -> str:
    examples = bundle.get("collateral_examples", {})
    ranked: list[tuple[int, str, dict]] = []
    for name, item in examples.items():
        excerpt = (item.get("text") or "").strip()
        if not excerpt:
            continue
        score = _collateral_matches_query(
            name,
            excerpt,
            query,
            product_hint,
            audience_hint,
            example_id,
        )
        if score > 0:
            ranked.append((score, name, item))
    ranked.sort(key=lambda entry: (-entry[0], entry[1].lower()))
    parts: list[str] = []
    for _score, _name, item in ranked[:3]:
        excerpt = _extract_relevant_lines(item.get("text", ""), query, max_lines=28)
        if excerpt:
            parts.append(f"Example Collateral: {item['name']}\n\n{excerpt}")
    return "\n\n---\n\n".join(parts)


def general_grounding_block(proof_posture: str = "strict-default") -> str:
    data = load_grounding()
    public_stats = list(data.get("default_public_stats", DEFAULT_PUBLIC_STATS))
    if proof_posture == "contextual-allowed":
        public_stats.extend(data.get("contextual_stats", CONTEXTUAL_STATS))
    public_stats_block = "\n".join(f"- {item}" for item in public_stats)
    contextual_note = (
        "Contextual approved stats may be used only when the request and support materials clearly justify them."
        if proof_posture == "contextual-allowed"
        else "Do not use contextual approved stats unless they are explicitly warranted by the request and support material."
    )
    return f"""Document: {data['source']['title']}
Last reviewed: {data['source']['last_reviewed']}
Grounding mode: {data.get('mode', 'live')}
Grounding scope: live Vocareum product catalog, approved email examples, and example collateral

Catalog front matter:
{data['catalog_front_matter'].strip() or "Use the live catalog as the governing source of truth."}

Approved public stats:
{public_stats_block}

Proof rule:
{contextual_note}
"""


def grounding_block(
    user_text: str,
    asset_type: str = "custom",
    example: dict | None = None,
    *,
    audience_door: str = "",
    proof_posture: str = "strict-default",
) -> str:
    data = load_grounding()
    sections: list[str] = []
    product_block = product_grounding_block(user_text)
    if product_block:
        sections.append(f"Relevant live product catalog sections:\n{product_block}")

    example_id = example.get("id", "") if example else ""
    if example and asset_type in {
        "outreach-email",
        "follow-up-email",
        "capability-boundary-email",
        "partner-email",
        "custom",
    }:
        email_block = _email_example_block(example_id, data)
        if email_block:
            sections.append(email_block)

    if asset_type in {"one-pager", "overview-collateral", "sales-deck-brief", "website-copy", "custom"}:
        product_matches = matched_products(user_text)
        product_hint = product_matches[0] if product_matches else ""
        collateral_block = _collateral_example_block(
            example_id,
            data,
            user_text,
            product_hint,
            audience_door,
        )
        if collateral_block:
            sections.append(collateral_block)

    if not sections:
        return general_grounding_block(proof_posture)

    stats = list(data.get("default_public_stats", DEFAULT_PUBLIC_STATS))
    if proof_posture == "contextual-allowed":
        stats.extend(data.get("contextual_stats", CONTEXTUAL_STATS))
    stats_block = "\n".join(f"- {item}" for item in stats)
    warnings = data.get("warnings", [])
    warning_block = "\n".join(f"- {item}" for item in warnings) if warnings else "- none"

    joined_sections = "\n\n===\n\n".join(sections)
    return f"""Document: {data['source']['title']}
Last reviewed: {data['source']['last_reviewed']}
Grounding mode: {data.get('mode', 'live')}
Grounding scope: use the live sources below as primary truth

Grounding warnings:
{warning_block}

Default public stats:
{stats_block}

{joined_sections}
"""
