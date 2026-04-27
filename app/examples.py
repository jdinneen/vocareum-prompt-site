from __future__ import annotations

from functools import lru_cache

DELIVERABLE_TYPES = [
    {
        "id": "outreach-email",
        "label": "Outreach email",
        "group": "email",
        "description": "Net-new buyer or prospect email grounded in approved product truth.",
    },
    {
        "id": "follow-up-email",
        "label": "Follow-up email",
        "group": "email",
        "description": "Post-demo, post-meeting, or positive-reply follow-up.",
    },
    {
        "id": "capability-boundary-email",
        "label": "Capability boundary email",
        "group": "email",
        "description": "Plain correction when a buyer assumes a capability exists.",
    },
    {
        "id": "partner-email",
        "label": "Partner framing email",
        "group": "email",
        "description": "Narrative or case-study email for partners and co-marketing threads.",
    },
    {
        "id": "one-pager",
        "label": "One-pager copy",
        "group": "collateral",
        "description": "Structured one-pager copy following the approved collateral patterns.",
    },
    {
        "id": "overview-collateral",
        "label": "Overview collateral",
        "group": "collateral",
        "description": "Product or company overview copy with proof and capability structure.",
    },
    {
        "id": "sales-deck-brief",
        "label": "Sales deck brief",
        "group": "collateral",
        "description": "Slide-by-slide outline for a sales or discussion deck.",
    },
    {
        "id": "website-copy",
        "label": "Website copy",
        "group": "collateral",
        "description": "Homepage or landing-page copy grounded in product and proof.",
    },
    {
        "id": "custom",
        "label": "Custom",
        "group": "custom",
        "description": "Freeform prompt with optional example-pattern steering.",
    },
]

EXAMPLE_PATTERNS = [
    {
        "id": "governed-model-access",
        "label": "Governed model access reply",
        "group": "email",
        "asset_types": ["outreach-email", "follow-up-email", "custom"],
        "use_when": "A buyer asks whether Vocareum can provide model access, API keys, or direct chat access for students.",
        "structure": [
            "Open by acknowledging the question directly.",
            "Answer capability questions in plain language.",
            "State the boundary clearly when Vocareum does not provide consumer-seat resale.",
            "Close with a concrete invitation to discuss further.",
        ],
        "claims_to_keep": [
            "Scoped model access through AI Gateway.",
            "Per-learner budget caps, usage logging, and policy controls.",
            "Support for major model providers when grounded in catalog truth.",
        ],
        "claims_to_avoid": [
            "Do not imply Vocareum resells ChatGPT or Claude consumer seats.",
            "Do not imply a shrink-wrapped product if the experience is tailored.",
        ],
        "source": "Approved Email Material: AI Gateway / Governed Model Access",
    },
    {
        "id": "short-demo-follow-up",
        "label": "Short post-demo add-on",
        "group": "email",
        "asset_types": ["follow-up-email", "custom"],
        "use_when": "The core explanation is already covered and you only need a short strategic expansion note.",
        "structure": [
            "Add one concrete use-case or event-specific signal.",
            "Keep the note short.",
            "End with a simple ask.",
        ],
        "claims_to_keep": [
            "Reference concrete use cases discussed live.",
            "Keep the ask simple and direct.",
        ],
        "claims_to_avoid": [
            "Do not overstate opportunity stage or product commitment.",
        ],
        "source": "Approved Email Material: Short Strategic Add-On After Demo",
    },
    {
        "id": "capability-boundary",
        "label": "Capability boundary reset",
        "group": "email",
        "asset_types": ["capability-boundary-email", "custom"],
        "use_when": "A customer assumes a capability exists and you need to correct that quickly.",
        "structure": [
            "State the limit plainly in the first line.",
            "Ask the next diagnostic question immediately.",
            "Do not over-explain.",
        ],
        "claims_to_keep": [
            "State the actual supported limit clearly.",
        ],
        "claims_to_avoid": [
            "Do not soften the answer so much that the customer thinks the capability exists.",
        ],
        "source": "Approved Email Material: Supported Today / Capability-Boundary Reply",
    },
    {
        "id": "partner-case-study",
        "label": "Partner case-study framing",
        "group": "email",
        "asset_types": ["partner-email", "custom"],
        "use_when": "A partner asks for narrative structure, industry challenge, or case-study framing.",
        "structure": [
            "Frame the industry challenge first.",
            "Describe the solution as a partner-plus-Vocareum operating model.",
            "List the key themes that should anchor the asset.",
            "Close by inviting feedback or alignment.",
        ],
        "claims_to_keep": [
            "Operational control.",
            "Governance without compromising learner experience.",
            "Repeatability.",
            "Real environments.",
        ],
        "claims_to_avoid": [
            "Do not add unapproved metrics or technical details.",
            "Do not use retired moat language as the headline.",
        ],
        "source": "Approved Email Material: Partner Case-Study Framing",
    },
    {
        "id": "scheduling-follow-up",
        "label": "Positive scheduling follow-up",
        "group": "email",
        "asset_types": ["follow-up-email", "custom"],
        "use_when": "A prospect already wants a next meeting and just needs scheduling.",
        "structure": [
            "Confirm interest.",
            "Offer concrete dates.",
            "Ask for a preferred slot or alternatives.",
        ],
        "claims_to_keep": [
            "Make scheduling easy and direct.",
        ],
        "claims_to_avoid": [
            "Do not restart the pitch once the buyer already wants to meet.",
        ],
        "source": "Approved Email Material: Scheduling / Positive Follow-Up Reply",
    },
    {
        "id": "post-event-follow-up",
        "label": "Strategic post-event follow-up",
        "group": "email",
        "asset_types": ["follow-up-email", "partner-email", "custom"],
        "use_when": "You met a strategic prospect or ecosystem partner at an event and want a concrete next meeting.",
        "structure": [
            "Anchor the note in the real event meeting.",
            "Reference a real internal follow-up session.",
            "Name the actual product area or workflow under discussion.",
            "Ask for a concrete next meeting.",
        ],
        "claims_to_keep": [
            "Recent meeting context.",
            "Actual product area or workflow.",
            "Specific follow-up ask.",
        ],
        "claims_to_avoid": [
            "Do not imply a formal partnership or approved roadmap.",
            "Do not overstate what was agreed in the first meeting.",
        ],
        "source": "Approved Email Material: Strategic Post-Event Follow-Up",
    },
    {
        "id": "aws-cosell-one-pager",
        "label": "AWS co-sell one-pager",
        "group": "collateral",
        "asset_types": ["one-pager", "overview-collateral", "custom"],
        "use_when": "You need a one-page product or solution asset with a sharp hero, stat bar, workflow, proof, and partner/customer value split.",
        "structure": [
            "Hero banner with a clear product name, audience, and one-sentence value proposition.",
            "Stat bar with three to four grounded proof points.",
            "Problem section with direct pain framing.",
            "How It Works as numbered steps.",
            "Coverage or persona table when relevant.",
            "Named proof quote or proof bar.",
            "Split value framing such as For Partner / For Customer.",
        ],
        "claims_to_keep": [
            "Use a strong proof point early.",
            "Prefer real environments and governance language when supported.",
            "Keep one clear CTA or closing action.",
        ],
        "claims_to_avoid": [
            "Do not invent metrics or named proof.",
            "Do not let generic company scale replace product explanation.",
        ],
        "source": "Example Collateral: Vocareum_On_the_Fly_Labs_AWS_Co_Sell.pdf and local HTML copy",
    },
    {
        "id": "method-one-pager",
        "label": "Methodology one-pager",
        "group": "collateral",
        "asset_types": ["one-pager", "overview-collateral", "custom"],
        "use_when": "You need a one-pager centered on a method, process, or repeatable operating model.",
        "structure": [
            "Lead with one hero stat or proof anchor.",
            "Use numbered steps for the method.",
            "Support with one named case study or proof example.",
            "Keep the rhythm: headline, proof, explanation, supporting detail, CTA.",
        ],
        "claims_to_keep": [
            "Numbered steps.",
            "Named case study or proof when available.",
        ],
        "claims_to_avoid": [
            "Do not bury the method under generic company description.",
        ],
        "source": "Reference Collateral note: Learning Flow Method One-Pager",
    },
    {
        "id": "product-overview",
        "label": "Product overview collateral",
        "group": "collateral",
        "asset_types": ["overview-collateral", "website-copy", "sales-deck-brief", "custom"],
        "use_when": "You need a fuller product or company overview asset.",
        "structure": [
            "Lead with a strong value proposition and proof.",
            "Use tables for product categories or capabilities where useful.",
            "Include a customer quote or named proof block.",
            "Make the asset easy to scan by solution family or audience.",
        ],
        "claims_to_keep": [
            "Lab categories or capability groupings.",
            "Platform capabilities.",
            "Named quote or proof anchor.",
        ],
        "claims_to_avoid": [
            "Do not turn every product into one blended surface.",
        ],
        "source": "Reference Collateral note: Vocareum Overview Q1 2026",
    },
    {
        "id": "sales-collateral",
        "label": "Sales collateral / deck pattern",
        "group": "collateral",
        "asset_types": ["sales-deck-brief", "overview-collateral", "custom"],
        "use_when": "You need a sales deck, portfolio story, or broader market-facing collateral brief.",
        "structure": [
            "Open with market segment or buyer context.",
            "Show product portfolio or solution family structure.",
            "Use proof points and named customers where grounded.",
            "Close with the next conversation or CTA.",
        ],
        "claims_to_keep": [
            "Market segments.",
            "Product portfolio structure.",
            "Proof points.",
        ],
        "claims_to_avoid": [
            "Do not use unsupported market leadership claims.",
        ],
        "source": "Reference Collateral note: Vocareum Sales Collateral",
    },
]


@lru_cache(maxsize=1)
def deliverable_map() -> dict[str, dict]:
    return {item["id"]: item for item in DELIVERABLE_TYPES}


@lru_cache(maxsize=1)
def example_map() -> dict[str, dict]:
    return {item["id"]: item for item in EXAMPLE_PATTERNS}


def examples_for(asset_type: str) -> list[dict]:
    if not asset_type or asset_type == "custom":
        return EXAMPLE_PATTERNS
    return [item for item in EXAMPLE_PATTERNS if asset_type in item["asset_types"]]


def resolve_example(example_pattern: str, asset_type: str, objective: str) -> dict | None:
    if example_pattern and example_pattern in example_map():
        return example_map()[example_pattern]

    lowered = objective.lower()
    if asset_type in {"capability-boundary-email"}:
        return example_map()["capability-boundary"]
    if asset_type in {"partner-email"}:
        if "event" in lowered or "asu" in lowered or "conference" in lowered:
            return example_map()["post-event-follow-up"]
        return example_map()["partner-case-study"]
    if asset_type in {"follow-up-email"}:
        if "schedule" in lowered or "calendar" in lowered or "meeting" in lowered:
            return example_map()["scheduling-follow-up"]
        if "event" in lowered or "asu" in lowered or "conference" in lowered:
            return example_map()["post-event-follow-up"]
        return example_map()["short-demo-follow-up"]
    if asset_type in {"outreach-email"}:
        if any(term in lowered for term in ("api key", "chatgpt", "claude", "gemini", "model access", "gateway")):
            return example_map()["governed-model-access"]
        return None
    if asset_type in {"one-pager"}:
        if "aws" in lowered or "co-sell" in lowered or "on-the-fly" in lowered:
            return example_map()["aws-cosell-one-pager"]
        return example_map()["method-one-pager"]
    if asset_type in {"overview-collateral", "website-copy"}:
        return example_map()["product-overview"]
    if asset_type in {"sales-deck-brief"}:
        return example_map()["sales-collateral"]
    return None


def example_prompt_block(example: dict | None) -> str:
    if not example:
        return ""
    structure = "\n".join(f"- {item}" for item in example["structure"])
    keep = "\n".join(f"- {item}" for item in example["claims_to_keep"])
    avoid = "\n".join(f"- {item}" for item in example["claims_to_avoid"])
    return f"""Example pattern to emulate:
Name: {example['label']}
Source: {example['source']}
Use when: {example['use_when']}

Structure to follow:
{structure}

Claims to keep:
{keep}

Claims to avoid:
{avoid}
"""
