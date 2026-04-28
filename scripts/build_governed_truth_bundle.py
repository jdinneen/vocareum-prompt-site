from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SITE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = SITE_ROOT / "app" / "data" / "governed_truth_bundle.json"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
APPROVED_NUMERIC_PATH = REPO_ROOT / "core" / "shared_rules" / "email" / "approved_numeric_claims.json"
APPROVED_LINKS_PATH = REPO_ROOT / "core" / "shared_rules" / "email" / "approved_links.json"


def _parse_agents_table(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        parts = [piece.strip() for piece in line.strip().strip("|").split("|")]
        if len(parts) != 2:
            continue
        metric, value = parts
        if metric in {"Metric", "--------"} or value == "---------------":
            continue
        rows[metric] = value
    return rows


def _split_csvish(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_truth_bundle() -> dict:
    agents_text = AGENTS_PATH.read_text(encoding="utf-8")
    stats_rows = _parse_agents_table(agents_text)
    approved_numeric = json.loads(APPROVED_NUMERIC_PATH.read_text(encoding="utf-8"))
    approved_links = json.loads(APPROVED_LINKS_PATH.read_text(encoding="utf-8"))

    annual_unique = stats_rows.get("Annual unique learners", "1M+").split(" ")[0]
    default_public_stats = [
        f"{stats_rows.get('AWS learners', '2M+')} AWS learners",
        f"{annual_unique} annual unique learners",
        f"{stats_rows.get('Total platform learners', '5M+')} total platform learners",
        f"{stats_rows.get('Institutions/organizations', '7,000+')} institutions and organizations",
    ]

    approved_named_proof = (
        _split_csvish(stats_rows.get("Key partners", ""))
        + _split_csvish(stats_rows.get("Enterprise examples", ""))
        + _split_csvish(stats_rows.get("Academic examples", ""))
    )

    allowed_reference_names = [
        "Vocareum",
        "AI Gateway",
        "AI Notebook",
        "AI Compass",
        "Cloud Labs",
        "Developer Workspaces",
        "Virtual Desktop",
        "Agentic AI Labs",
        "On-the-Fly Labs",
        "Simulations",
        "Databases",
        "GPU & CPU Compute",
        "Cyber Ranges",
        "Platform Enablement Labs",
        "OpenAI",
        "Anthropic",
        "Google Gemini",
        "AWS Bedrock",
        "Azure OpenAI",
        "Claude Code",
        "GitHub Copilot",
        "Amazon Q",
        "OpenAI Codex",
        "AWS",
        "Azure",
        "GCP",
        "Databricks",
        "SOC 2 Type II",
        "FERPA",
        "GDPR",
        "WCAG 2.1 AA",
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": [
            "AGENTS.md",
            "core/shared_rules/email/approved_numeric_claims.json",
            "core/shared_rules/email/approved_links.json",
        ],
        "default_public_stats": default_public_stats,
        "approved_numeric_claims": approved_numeric.get("claims", []),
        "approved_named_proof": approved_named_proof,
        "approved_links": approved_links,
        "allowed_reference_names": allowed_reference_names,
        "supported_cloud_platforms": _split_csvish(stats_rows.get("Cloud providers supported", "")),
        "approved_compliance": _split_csvish(stats_rows.get("Compliance", "")),
        "approved_model_providers": [
            "OpenAI",
            "Anthropic",
            "Google Gemini",
            "AWS Bedrock",
            "Azure OpenAI",
        ],
        "approved_agentic_tools": [
            "Claude Code",
            "GitHub Copilot",
            "Amazon Q",
            "OpenAI Codex",
        ],
        "supported_workflows": [
            "outbound-email",
            "reply-email",
            "sales-collateral",
        ],
    }


def main() -> None:
    bundle = build_truth_bundle()
    OUTPUT_PATH.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
