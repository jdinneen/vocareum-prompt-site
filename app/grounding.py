from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
GROUNDING_FILE = APP_DIR / "data" / "grounding_snapshot.json"
CATALOG_FILE = APP_DIR / "data" / "product_catalog_v1.1.md"

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
    "Custom Virtual Labs": ("custom virtual labs", "custom virtual lab"),
    "Platform Enablement Labs": ("platform enablement labs", "platform enablement lab"),
}


@lru_cache(maxsize=1)
def load_grounding() -> dict:
    return json.loads(GROUNDING_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_catalog_text() -> str:
    return CATALOG_FILE.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def catalog_sections() -> dict[str, str]:
    text = load_catalog_text()
    pattern = re.compile(r"^# \*\*(.+?)\*\*\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


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
    sections = catalog_sections()
    blocks: list[str] = []
    for product in matches[:3]:
        section = sections.get(product, "").strip()
        if section:
            blocks.append(section)
    return "\n\n---\n\n".join(blocks)


def general_grounding_block() -> str:
    data = load_grounding()
    public_stats = "\n".join(f"- {item}" for item in data["public_stats"])
    audience_segments = "\n".join(
        f"- {item['name']} ({', '.join(item['examples'])}): {item['positioning']}"
        for item in data["audience_segments"]
    )
    products = "\n".join(
        f"- {item['name']}: {item['summary']}"
        for item in data["products"]
    )
    proof = "\n".join(
        f"- {item['name']}: {item['anchor']}"
        for item in data["proof_anchors"]
    )
    style = "\n".join(f"- {item}" for item in data["style_rules"])

    return f"""Document: {data['source']['title']}
Last reviewed: {data['source']['last_reviewed']}
Grounding scope: governed Vocareum product, proof, and style guidance

Public stats:
{public_stats}

Audience segments:
{audience_segments}

Core product surfaces:
{products}

Proof anchors:
{proof}

Style rules:
{style}
"""


def grounding_block(user_text: str) -> str:
    product_block = product_grounding_block(user_text)
    if product_block:
        data = load_grounding()
        return f"""Document: {data['source']['title']}
Last reviewed: {data['source']['last_reviewed']}
Grounding scope: use the exact product catalog section below as primary truth

Relevant product catalog sections:
{product_block}
"""
    return general_grounding_block()
