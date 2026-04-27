from __future__ import annotations

import io
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
    for line in text.splitlines():
        cleaned = _strip_markdown_decoration(line)
        if cleaned:
            return cleaned
    return "Vocareum Product & Feature Catalog"


def _fallback_bundle() -> dict:
    try:
        snapshot = json.loads(GROUNDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        snapshot = {
            "source": {
                "title": "Vocareum Product & Feature Catalog",
                "last_reviewed": "Unknown",
                "doc_url": f"https://docs.google.com/document/d/{VOC_PRODUCT_CATALOG_DOC_ID}/edit",
            },
            "public_stats": [
                "Since 2012",
                "50M+ learner labs launched",
                "5M+ learners served",
                "7,000+ institutions and organizations",
                "1M+ annual unique learners",
                "2M+ AWS learners",
            ],
            "style_palette": STYLE_PALETTE,
        }

    catalog_text = CATALOG_FILE.read_text(encoding="utf-8") if CATALOG_FILE.exists() else ""
    catalog_front_matter, catalog_sections = _parse_named_sections(catalog_text, PRODUCT_SECTION_TITLES)
    return {
        "source": snapshot["source"],
        "catalog_front_matter": catalog_front_matter,
        "catalog_sections": catalog_sections,
        "email_sections": {},
        "collateral_examples": {},
        "public_stats": snapshot.get(
            "public_stats",
            [
                "Since 2012",
                "50M+ learner labs launched",
                "5M+ learners served",
                "7,000+ institutions and organizations",
                "1M+ annual unique learners",
                "2M+ AWS learners",
            ],
        ),
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

    source = {
        "title": _parse_title(catalog_text) or "Vocareum Product & Feature Catalog (Doc)",
        "last_reviewed": _parse_last_reviewed(catalog_text),
        "doc_url": f"https://docs.google.com/document/d/{VOC_PRODUCT_CATALOG_DOC_ID}/edit",
    }
    return {
        "source": source,
        "catalog_front_matter": catalog_front_matter,
        "catalog_sections": catalog_sections,
        "email_sections": email_sections,
        "collateral_examples": collateral_examples,
        "public_stats": [
            "Since 2012",
            "50M+ learner labs launched",
            "5M+ learners served",
            "7,000+ institutions and organizations",
            "1M+ annual unique learners",
            "2M+ AWS learners",
        ],
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
    except Exception:
        fresh_bundle = _fallback_bundle()

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
    return f"Approved Email Material example:\nSource: {section_title}\n\n{section}"


def _collateral_example_block(example_id: str, bundle: dict) -> str:
    names = COLLATERAL_FILES_BY_PATTERN.get(example_id, [])
    if not names:
        return ""
    parts: list[str] = []
    for name in names:
        item = bundle["collateral_examples"].get(name)
        if not item:
            continue
        excerpt = (item.get("text") or "").strip()
        if excerpt:
            parts.append(f"Example Collateral: {item['name']}\n\n{excerpt[:5000]}")
    return "\n\n---\n\n".join(parts)


def general_grounding_block() -> str:
    data = load_grounding()
    public_stats = "\n".join(f"- {item}" for item in data["public_stats"])
    return f"""Document: {data['source']['title']}
Last reviewed: {data['source']['last_reviewed']}
Grounding scope: live Vocareum product catalog, approved email examples, and example collateral

Catalog front matter:
{data['catalog_front_matter'].strip() or "Use the live catalog as the governing source of truth."}

Approved public stats:
{public_stats}
"""


def grounding_block(user_text: str, asset_type: str = "custom", example: dict | None = None) -> str:
    data = load_grounding()
    sections: list[str] = []
    product_block = product_grounding_block(user_text)
    if product_block:
        sections.append(f"Relevant live product catalog sections:\n{product_block}")

    if example:
        example_id = example.get("id", "")
        if asset_type in {
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
            collateral_block = _collateral_example_block(example_id, data)
            if collateral_block:
                sections.append(collateral_block)

    if not sections:
        return general_grounding_block()

    joined_sections = "\n\n===\n\n".join(sections)
    return f"""Document: {data['source']['title']}
Last reviewed: {data['source']['last_reviewed']}
Grounding scope: use the live sources below as primary truth

{joined_sections}
"""
