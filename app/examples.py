from __future__ import annotations

from functools import lru_cache


DELIVERABLE_TYPES = [
    {
        "id": "outbound-email",
        "label": "Outbound email",
        "description": "Net-new outbound email grounded in the live catalog and approved email examples.",
    },
    {
        "id": "reply-email",
        "label": "Reply to email thread",
        "description": "Best reply when a user pastes the incoming thread or email context into the brief.",
    },
    {
        "id": "sales-collateral",
        "label": "Overview collateral",
        "description": "Structured overview with headline, capabilities, buyers, proof, and CTA.",
    },
    {
        "id": "one-pager",
        "label": "One-pager",
        "description": "Full one-pager with hero, stat bar, problem, how-it-works steps, buyers, proof, and CTA.",
    },
    {
        "id": "sales-deck-brief",
        "label": "6-slide deck",
        "description": "Six-slide presentation outline with structured bullets per slide.",
    },
]

EXAMPLE_PATTERNS = [
    {
        "id": "governed-model-access",
        "label": "Governed model access reply",
        "group": "email",
        "asset_types": ["outbound-email", "reply-email"],
        "use_when": "A buyer asks whether Vocareum can provide model access, API keys, or direct chat access for students.",
        "structure": [
            "Answer capability questions directly.",
            "State the boundary clearly when Vocareum does not provide consumer-seat resale.",
            "Close with a concrete next-step ask.",
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
        "id": "capability-boundary",
        "label": "Capability boundary reset",
        "group": "email",
        "asset_types": ["reply-email"],
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
        "id": "short-demo-follow-up",
        "label": "Short post-demo add-on",
        "group": "email",
        "asset_types": ["reply-email"],
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
        "id": "scheduling-follow-up",
        "label": "Positive scheduling follow-up",
        "group": "email",
        "asset_types": ["reply-email"],
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
        "id": "partner-case-study",
        "label": "Partner case-study framing",
        "group": "email",
        "asset_types": ["outbound-email", "reply-email"],
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
        ],
        "source": "Approved Email Material: Partner Case-Study Framing",
    },
    {
        "id": "post-event-follow-up",
        "label": "Strategic post-event follow-up",
        "group": "email",
        "asset_types": ["reply-email"],
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
        ],
        "source": "Approved Email Material: Strategic Post-Event Follow-Up",
    },
    {
        "id": "aws-cosell-one-pager",
        "label": "AWS co-sell one-pager",
        "group": "collateral",
        "asset_types": ["sales-collateral", "one-pager"],
        "use_when": "You need a one-page product or solution asset with a sharp hero, stat bar, workflow, proof, and partner/customer value split.",
        "structure": [
            "Lead with a clear audience and value proposition.",
            "Use a concise stat bar with grounded proof only.",
            "Explain the operating model and best-fit buyer cleanly.",
        ],
        "claims_to_keep": [
            "Use a strong proof point early.",
            "Prefer real environments and governance language when supported.",
        ],
        "claims_to_avoid": [
            "Do not invent metrics or named proof.",
        ],
        "source": "Example Collateral: Vocareum_On_the_Fly_Labs_AWS_Co_Sell.pdf",
    },
    {
        "id": "method-one-pager",
        "label": "Methodology one-pager",
        "group": "collateral",
        "asset_types": ["sales-collateral", "one-pager"],
        "use_when": "You need a one-pager centered on a method, process, or repeatable operating model.",
        "structure": [
            "Lead with one hero proof anchor.",
            "Use numbered steps for the method.",
            "Support with one approved named proof example when relevant.",
        ],
        "claims_to_keep": [
            "Numbered steps.",
            "Approved named proof when it directly strengthens the asset.",
        ],
        "claims_to_avoid": [
            "Do not bury the method under generic company description.",
        ],
        "source": "Reference Collateral: Learning Flow Method One-Pager",
    },
    {
        "id": "reference-one-pager",
        "label": "Reference one-pager",
        "group": "collateral",
        "asset_types": ["one-pager"],
        "use_when": "You need a CEO-ready one-pager with a crisp buyer story, grounded proof discipline, and one clean CTA.",
        "structure": [
            "Lead with one named audience and one clear outcome.",
            "Use 1 to 3 credible buyer roles only when the brief or grounding supports them.",
            "Keep proof disciplined: one approved named proof when available, otherwise `Proof: None`.",
            "Close with a single next step.",
        ],
        "claims_to_keep": [
            "Named audience specificity.",
            "Approved public stats only when they help the story.",
            "Grounded operating-model language.",
        ],
        "claims_to_avoid": [
            "Do not coin buyer labels from product names or internal jargon.",
            "Do not broaden one named audience into generic sectors.",
            "Do not use placeholder proof, source metadata, or process language as public proof.",
        ],
        "source": "Reference Collateral: Learning Flow Method One-Pager + Vocareum Overview Q1 2026",
    },
    {
        "id": "product-overview",
        "label": "Product overview collateral",
        "group": "collateral",
        "asset_types": ["sales-collateral"],
        "use_when": "You need a fuller product or company overview asset.",
        "structure": [
            "Lead with a strong value proposition and proof.",
            "Use grouped capabilities and buyer fit.",
            "Keep proof paraphrased and grounded.",
        ],
        "claims_to_keep": [
            "Platform capabilities.",
            "Paraphrased approved proof anchor.",
        ],
        "claims_to_avoid": [
            "Do not turn every product into one blended surface.",
        ],
        "source": "Reference Collateral: Vocareum Overview Q1 2026",
    },
    {
        "id": "sales-collateral",
        "label": "Sales collateral / deck pattern",
        "group": "collateral",
        "asset_types": ["sales-collateral"],
        "use_when": "You need a sales-facing story with market context, product structure, and proof.",
        "structure": [
            "Open with buyer context.",
            "Show product portfolio or solution family structure.",
            "Use approved proof points only.",
            "Close with the next conversation.",
        ],
        "claims_to_keep": [
            "Market segments.",
            "Product portfolio structure.",
            "Proof points.",
        ],
        "claims_to_avoid": [
            "Do not use unsupported market leadership claims.",
        ],
        "source": "Reference Collateral: Vocareum Sales Collateral",
    },
]


@lru_cache(maxsize=1)
def example_map() -> dict[str, dict]:
    return {item["id"]: item for item in EXAMPLE_PATTERNS}


def resolve_example(asset_type: str, objective: str) -> dict | None:
    lowered = objective.lower()
    if asset_type == "outbound-email":
        if any(term in lowered for term in ("partner", "case study", "co-sell", "joint")):
            return example_map()["partner-case-study"]
        if any(term in lowered for term in ("api key", "chatgpt", "claude", "gemini", "model access", "gateway")):
            return example_map()["governed-model-access"]
        return example_map()["governed-model-access"]

    if asset_type == "reply-email":
        if any(term in lowered for term in ("do you support", "can you provide", "can we use", "not supported", "unsupported")):
            return example_map()["capability-boundary"]
        if any(term in lowered for term in ("schedule", "calendar", "meeting", "next week", "time on")):
            return example_map()["scheduling-follow-up"]
        if any(term in lowered for term in ("asu", "gsv", "conference", "event")):
            return example_map()["post-event-follow-up"]
        if any(term in lowered for term in ("partner", "case study", "narrative", "co-market")):
            return example_map()["partner-case-study"]
        return example_map()["short-demo-follow-up"]

    if asset_type == "one-pager":
        if any(term in lowered for term in ("aws", "co-sell", "on-the-fly")):
            return example_map()["aws-cosell-one-pager"]
        if any(term in lowered for term in ("method", "workflow", "operating model")):
            return example_map()["method-one-pager"]
        return example_map()["reference-one-pager"]

    if asset_type in {"sales-collateral", "sales-deck-brief"}:
        if any(term in lowered for term in ("aws", "co-sell", "on-the-fly")):
            return example_map()["aws-cosell-one-pager"]
        if any(term in lowered for term in ("method", "workflow", "operating model")):
            return example_map()["method-one-pager"]
        if any(term in lowered for term in ("deck", "portfolio", "market segment")):
            return example_map()["sales-collateral"]
        return example_map()["product-overview"]

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
