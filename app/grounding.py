from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
GROUNDING_FILE = APP_DIR / "data" / "grounding_snapshot.json"


@lru_cache(maxsize=1)
def load_grounding() -> dict:
    return json.loads(GROUNDING_FILE.read_text(encoding="utf-8"))


def grounding_block() -> str:
    data = load_grounding()
    public_stats = "\n".join(f"- {item}" for item in data["public_stats"])
    icp_verticals = "\n".join(
        f"- {item['name']}: {', '.join(item['examples'])}"
        for item in data["icp_verticals"]
    )
    audience_doors = "\n".join(
        f"- {item['name']}: {item['positioning']}"
        for item in data["audience_doors"]
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

ICP verticals:
{icp_verticals}

Audience doors:
{audience_doors}

Core product surfaces:
{products}

Proof anchors:
{proof}

Style rules:
{style}
"""
