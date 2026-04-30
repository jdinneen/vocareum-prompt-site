from __future__ import annotations

import re
from dataclasses import dataclass


NUMBER_PHRASE_RE = re.compile(
    r"\$?\d[\d,]*(?::\d{2})?(?:\.\d+)?(?:\+|%|[kKmMbB])?(?:\s+[A-Za-z][A-Za-z0-9/+-]*){0,4}"
)
NAME_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9.+&/-]*)(?:\s+(?:of|and|for|the|&)?\s*[A-Z][A-Za-z0-9.+&/-]*)+\b"
)
CLAIM_VERBS = {
    "supports",
    "support",
    "provides",
    "provide",
    "includes",
    "include",
    "delivers",
    "deliver",
    "enables",
    "enable",
    "allows",
    "allow",
    "offers",
    "offer",
    "gives",
    "give",
    "routes",
    "route",
    "manages",
    "manage",
    "governs",
    "govern",
    "integrates",
    "integrate",
    "works with",
}
PROOF_CUES = {
    "proof",
    "customer",
    "case study",
    "deployment",
    "example",
    "examples include",
    "used by",
    "partnership",
    "rollout",
    "partnered with",
    "partnered",
}
IGNORED_SENTENCE_PREFIXES = (
    "hi ",
    "hello ",
    "thanks",
    "thank you",
    "best,",
    "regards,",
    "would you",
    "could you",
    "please",
    "happy to",
    "let me know",
)
STOPWORDS = {
    "about",
    "across",
    "after",
    "against",
    "also",
    "among",
    "been",
    "being",
    "between",
    "build",
    "built",
    "buyer",
    "buyers",
    "cloud",
    "course",
    "courses",
    "customer",
    "customers",
    "delivery",
    "email",
    "from",
    "governed",
    "into",
    "labs",
    "learning",
    "platform",
    "product",
    "program",
    "programs",
    "reply",
    "sales",
    "surface",
    "team",
    "their",
    "there",
    "these",
    "this",
    "through",
    "using",
    "with",
    "would",
    "your",
}


@dataclass
class ValidationIssue:
    code: str
    detail: str
    snippet: str


@dataclass
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().strip(".,:;()")).lower()


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\n+", "\n", text.strip())
    chunks = re.split(r"(?<=[.!?])\s+|\n", cleaned)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _extract_numeric_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    for match in NUMBER_PHRASE_RE.finditer(text):
        phrase = match.group(0).strip().strip(".,:;")
        if not any(ch.isdigit() for ch in phrase):
            continue
        phrases.append(phrase)
    return phrases


def _allowed_numeric_set(truth_bundle: dict, support_text: str) -> set[str]:
    allowed = {_normalize(item) for item in truth_bundle.get("approved_numeric_claims", [])}
    allowed.update(_normalize(item) for item in truth_bundle.get("default_public_stats", []))
    allowed.update(_normalize(item) for item in _extract_numeric_phrases(support_text))
    return {item for item in allowed if item}


def _numeric_phrase_allowed(normalized_phrase: str, allowed_numbers: set[str]) -> bool:
    if normalized_phrase in allowed_numbers:
        return True
    phrase_stem = re.match(r"^\$?\d[\d,]*(?::\d{2})?(?:\.\d+)?(?:\+|%|[kKmMbB])?(?:\s+(?:am|pm))?", normalized_phrase)
    for allowed in allowed_numbers:
        allowed_stem = re.match(r"^\$?\d[\d,]*(?::\d{2})?(?:\.\d+)?(?:\+|%|[kKmMbB])?(?:\s+(?:am|pm))?", allowed)
        if phrase_stem and allowed_stem and phrase_stem.group(0) == allowed_stem.group(0):
            return True
        if normalized_phrase.startswith(allowed) or allowed.startswith(normalized_phrase):
            return True
    return False


def _quote_issues(text: str) -> list[ValidationIssue]:
    if '"' in text or "“" in text or "”" in text:
        return [ValidationIssue("direct_quotes", "Direct quotes are not allowed in generated output.", text[:200])]
    return []


def _significant_tokens(sentence: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[a-z][a-z0-9+-]{3,}", sentence.lower()):
        if token in STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _sentence_needs_grounding(sentence: str) -> bool:
    lowered = sentence.lower()
    if lowered.startswith(IGNORED_SENTENCE_PREFIXES):
        return False
    return any(verb in lowered for verb in CLAIM_VERBS)


def _proof_context(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(cue in lowered for cue in PROOF_CUES)


SECTION_HEADER_PREFIXES = (
    "Subject",
    "Headline",
    "Subhead",
    "Core Capabilities",
    "Best-Fit",
    "How It Works",
    "Who Uses",
    "Stat Bar",
    "Call To",
    "Platform Reach",
    "Platform Scale",
    "Platform Overview",
    "Public Proof",
    "Proof and",
    "Proof Points",
    "Key Capabilities",
    "Key Features",
    "Use Cases",
    "Typical Use",
    "Source Links",
    "Slide ",
)


KNOWN_PRODUCT_FRAGMENTS = {
    "on-the-fly labs", "ai gateway", "ai compass", "ai notebook",
    "cloud labs", "developer workspaces", "virtual desktop",
    "agentic ai labs", "cyber ranges", "platform enablement",
    "vocareum",
}

MAX_PROOF_NAME_WORDS = 5
MIN_PROOF_NAME_WORDS = 2

# Common verbs/adjectives that start capitalized mid-sentence and look like names
# to the regex but are not proof references.
GENERIC_NAME_STARTS = {
    "Manages", "Provides", "Enables", "Supports", "Delivers", "Includes",
    "Offers", "Allows", "Routes", "Governs", "Integrates", "Deploys",
    "Configures", "Controls", "Enforces", "Prevents", "Reduces", "Tracks",
    "Each", "Every", "These", "Those", "Using", "Through", "Within",
    "Managed", "Governed", "Centralized", "Distributed", "Automated",
}
ABSTRACT_REFERENCE_WORDS = {
    "access",
    "adoption",
    "agent",
    "agents",
    "analytics",
    "automation",
    "capability",
    "capabilities",
    "compute",
    "control",
    "controls",
    "deployment",
    "deployments",
    "enablement",
    "experience",
    "experiences",
    "foundation",
    "governance",
    "governed",
    "infrastructure",
    "integration",
    "integrations",
    "management",
    "model",
    "models",
    "operations",
    "orchestration",
    "policy",
    "readiness",
    "resource",
    "resources",
    "routing",
    "sandbox",
    "sandboxes",
    "security",
    "support",
    "training",
    "unified",
    "usage",
    "utilization",
    "visibility",
    "workflow",
    "workflows",
}
ENTITY_HINT_WORDS = {
    "academy",
    "classroom",
    "college",
    "district",
    "institute",
    "pilot",
    "school",
    "university",
}
TRAILING_REFERENCE_WORDS = {
    "case",
    "deployment",
    "integration",
    "partnership",
    "pilot",
    "platform",
    "program",
    "rollout",
    "story",
    "study",
}


def _extract_name_candidates(sentence: str) -> list[str]:
    names = []
    for match in NAME_RE.finditer(sentence):
        candidate = match.group(0).strip(" .,:;()")
        if any(candidate.startswith(prefix) for prefix in SECTION_HEADER_PREFIXES):
            continue
        # Skip long descriptive titles — real named proof is short (org names).
        words = candidate.split()
        if len(words) > MAX_PROOF_NAME_WORDS:
            continue
        # Skip very short phrases where the first word is a generic verb/adjective.
        if len(words) <= MIN_PROOF_NAME_WORDS and words[0] in GENERIC_NAME_STARTS:
            continue
        # Skip references that contain a known product name.
        lowered = candidate.lower()
        if any(fragment in lowered for fragment in KNOWN_PRODUCT_FRAGMENTS):
            continue
        names.append(candidate)
    return names


def _reference_name_variants(candidate: str) -> set[str]:
    words = candidate.split()
    variants = {candidate.strip()}
    if words and words[0].lower() == "the":
        variants.add(" ".join(words[1:]).strip())
        words = words[1:]
    while words and words[-1].lower().strip(".,:;()") in TRAILING_REFERENCE_WORDS:
        words = words[:-1]
        trimmed = " ".join(words).strip()
        if trimmed:
            variants.add(trimmed)
    return {_normalize(item) for item in variants if item.strip()}


def _candidate_matches_allowed_name(candidate: str, names: set[str]) -> bool:
    normalized_names = {_normalize(name) for name in names if name.strip()}
    variants = _reference_name_variants(candidate)
    return any(
        variant == allowed
        or variant.startswith(f"{allowed} ")
        or allowed.startswith(f"{variant} ")
        for variant in variants
        for allowed in normalized_names
        if variant and allowed
    )


def _looks_like_descriptive_reference(candidate: str) -> bool:
    words = [token for token in re.findall(r"[A-Za-z0-9.+&/-]+", candidate) if token]
    lowered = [word.lower() for word in words]
    if len(lowered) < 2:
        return False
    if any(word in ENTITY_HINT_WORDS for word in lowered):
        return False
    if any(any(ch.isdigit() for ch in word) or "." in word or "&" in word for word in words):
        return False
    abstract_hits = sum(1 for word in lowered if word in ABSTRACT_REFERENCE_WORDS)
    if abstract_hits >= max(2, len(lowered) - 1):
        return True
    if lowered[0] in {word.lower() for word in GENERIC_NAME_STARTS} and abstract_hits >= 1:
        return True
    return False


def validate_output(
    *,
    asset_type: str,
    text: str,
    support_text: str,
    truth_bundle: dict,
    objective_text: str,
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    allowed_numbers = _allowed_numeric_set(truth_bundle, support_text + "\n" + objective_text)
    allowed_proof_names = {item.strip() for item in truth_bundle.get("approved_named_proof", []) if item.strip()}
    support_tokens = _significant_tokens(support_text + "\n" + objective_text)

    issues.extend(_quote_issues(text))

    for phrase in _extract_numeric_phrases(text):
        normalized = _normalize(phrase)
        if not _numeric_phrase_allowed(normalized, allowed_numbers):
            issues.append(
                ValidationIssue(
                    "unsupported_numbers",
                    f"Unsupported numeric claim: {phrase}",
                    phrase,
                )
            )

    # Grounded-answer mode paraphrases catalog content to answer questions.
    # Skip the claim-verb overlap check entirely for Q&A — it produces too
    # many false positives on natural paraphrasing.  Numeric, proof-name,
    # and quote checks still apply.
    is_answer_mode = asset_type == "grounded-answer"

    # Names from the user's objective are user-supplied context, not hallucinated proof.
    objective_names = {n for n in _extract_name_candidates(objective_text)}

    for sentence in _sentences(text):
        if _proof_context(sentence):
            for candidate in _extract_name_candidates(sentence):
                if _looks_like_descriptive_reference(candidate):
                    continue
                # Allow if the candidate matches an approved name exactly, or if
                # every proper-noun fragment in the candidate is individually approved
                # (handles "AWS Academy and DeepLearning.AI" as two approved names).
                if _candidate_matches_allowed_name(candidate, allowed_proof_names):
                    continue
                if allowed_proof_names and all(
                    any(name in candidate for name in allowed_proof_names)
                    for word in candidate.split(" and ")
                    if word.strip() and word.strip()[0].isupper()
                ):
                    continue
                # Allow names that appear in the user's objective (user-supplied context).
                if _candidate_matches_allowed_name(candidate, objective_names):
                    continue
                # Allow names that appear in the grounding support text.
                if any(variant in support_text.lower() for variant in _reference_name_variants(candidate)):
                    continue
                if True:
                    issues.append(
                        ValidationIssue(
                            "disallowed_named_proof",
                            f"Disallowed named proof or reference: {candidate}",
                            sentence[:240],
                        )
                    )
        if is_answer_mode:
            continue
        if not _sentence_needs_grounding(sentence):
            continue
        tokens = _significant_tokens(sentence)
        if len(tokens) < 3:
            continue
        overlap = tokens & support_tokens
        # Collateral formats paraphrase more than raw email; use a lower bar.
        is_collateral = asset_type in {"sales-collateral", "one-pager", "sales-deck-brief"}
        if is_collateral:
            min_overlap = 1 if len(tokens) <= 5 else max(2, (len(tokens) + 2) // 3)
        else:
            min_overlap = 1 if len(tokens) <= 4 else max(2, (len(tokens) + 1) // 2)
        if len(overlap) < min_overlap:
            issues.append(
                ValidationIssue(
                    "claims_not_in_grounding",
                    "Claim sentence is not sufficiently supported by the selected grounding.",
                    sentence[:240],
                )
            )

    # Deduplicate repeated issues with the same snippet.
    deduped: list[ValidationIssue] = []
    seen = set()
    for issue in issues:
        key = (issue.code, issue.snippet)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)

    return ValidationResult(ok=not deduped, issues=deduped)
