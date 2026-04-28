from fastapi.testclient import TestClient

from app.examples import DELIVERABLE_TYPES, EXAMPLE_PATTERNS
from app.grounding import SOURCE_TITLE, grounding_block
from app.main import (
    GenerateRequest,
    _build_user_prompt,
    _max_output_tokens,
    _sanitize_proof_sections,
    app,
)
from app.renderers import parse_deck_text, parse_overview_text
from app.validation import _extract_numeric_phrases, validate_output


def test_build_user_prompt_includes_example_grounding_excerpt(monkeypatch):
    monkeypatch.setattr(
        "app.grounding.load_grounding",
        lambda: {
            "source": {
                "title": SOURCE_TITLE,
                "last_reviewed": "2026-04-27",
                "doc_url": "https://example.com/catalog",
            },
            "mode": "live",
            "warnings": [],
            "catalog_front_matter": "Catalog front matter",
            "catalog_sections": {"On-the-Fly Labs": "On-the-Fly Labs\nGrounded section"},
            "email_sections": {},
            "collateral_examples": {
                "Vocareum_On_the_Fly_Labs_AWS_Co_Sell.pdf": {
                    "name": "Vocareum_On_the_Fly_Labs_AWS_Co_Sell.pdf",
                    "text": "AWS collateral example excerpt",
                },
                "Vocareum Overview Q1 2026": {
                    "name": "Vocareum Overview Q1 2026",
                    "text": "Overview collateral example excerpt",
                },
            },
            "truth_bundle": {
                "default_public_stats": ["2M+ AWS learners"],
                "approved_named_proof": ["AWS Academy"],
            },
            "style_palette": {},
        },
    )
    req = GenerateRequest(
        asset_type="sales-collateral",
        audience="AWS solutions architects",
        product="On-the-Fly Labs",
        objective="Create AWS sales collateral for On-the-Fly Labs workshop teams.",
        extra_constraints="Use grounded proof only.",
    )

    prompt = _build_user_prompt(req)

    assert "Workflow: sales-collateral" in prompt
    assert "Example Collateral: Vocareum_On_the_Fly_Labs_AWS_Co_Sell.pdf" in prompt
    assert "AWS collateral example excerpt" in prompt


def test_reply_prompt_requires_all_thread_asks(monkeypatch):
    monkeypatch.setattr(
        "app.grounding.load_grounding",
        lambda: {
            "source": {
                "title": SOURCE_TITLE,
                "last_reviewed": "2026-04-27",
                "doc_url": "https://example.com/catalog",
            },
            "mode": "live",
            "warnings": [],
            "catalog_front_matter": "Catalog front matter",
            "catalog_sections": {"AI Gateway": "AI Gateway\nGrounded section"},
            "email_sections": {},
            "collateral_examples": {},
            "truth_bundle": {
                "default_public_stats": ["2M+ AWS learners"],
                "approved_named_proof": ["AWS Academy"],
            },
            "style_palette": {},
        },
    )
    req = GenerateRequest(
        asset_type="reply-email",
        product="AI Gateway",
        objective="Thread: Can you provide ChatGPT access, and would next Tuesday at 5:00 PM work for a follow-up?",
    )

    prompt = _build_user_prompt(req)

    assert "If the thread contains more than one ask, answer all of them in the reply." in prompt
    assert "Explicitly identify every concrete ask in the thread and answer each one." in prompt


def test_grounding_block_uses_catalog_title_and_truth_bundle(monkeypatch):
    monkeypatch.setattr(
        "app.grounding.load_grounding",
        lambda: {
            "source": {
                "title": SOURCE_TITLE,
                "last_reviewed": "2026-04-27",
                "doc_url": "https://example.com/catalog",
            },
            "mode": "live",
            "warnings": ["example warning"],
            "catalog_front_matter": "Catalog front matter",
            "catalog_sections": {},
            "email_sections": {},
            "collateral_examples": {},
            "truth_bundle": {
                "default_public_stats": ["5M+ learners served"],
                "approved_named_proof": ["AWS Academy"],
            },
            "style_palette": {},
        },
    )

    prompt = grounding_block("general overview", "outbound-email")

    assert f"Document: {SOURCE_TITLE}" in prompt
    assert "example warning" in prompt
    assert "5M+ learners served" in prompt
    assert "AWS Academy" in prompt


def test_parse_deck_text_requires_exactly_six_slides():
    four_slide_text = "\n\n".join(
        [
            f"Slide {index}: Slide {index} title\n- Point one\n- Point two"
            for index in range(1, 5)
        ]
    )
    six_slide_text = "\n\n".join(
        [
            f"Slide {index}: Slide {index} title\n- Point one\n- Point two"
            for index in range(1, 7)
        ]
    )

    assert parse_deck_text(four_slide_text) is None
    parsed = parse_deck_text(six_slide_text)
    assert parsed is not None
    assert len(parsed["slides"]) == 6


def test_parse_overview_text_uses_current_sales_collateral_sections():
    text = (
        "Headline: Test\n\n"
        "Subhead: Grounded subhead\n\n"
        "Core Capabilities:\n- Governed access\n- Budget controls\n\n"
        "Best-Fit Buyers:\n- University AI teams\n- Platform operators\n\n"
        "Proof: Approved paraphrased proof.\n\n"
        "CTA: Schedule a review"
    )

    parsed = parse_overview_text(text)

    assert parsed is not None
    assert parsed["headline"] == "Test"
    assert parsed["capabilities"] == ["Governed access", "Budget controls"]
    assert parsed["buyers"] == ["University AI teams", "Platform operators"]


def test_meta_uses_default_public_stats_and_exposes_grounding_state(monkeypatch):
    monkeypatch.setattr(
        "app.main.load_grounding",
        lambda: {
            "source": {
                "title": SOURCE_TITLE,
                "last_reviewed": "2026-04-27",
                "doc_url": "https://example.com/catalog",
            },
            "mode": "live",
            "warnings": ["example warning"],
            "catalog_sections": {"AI Gateway": "section"},
            "truth_bundle": {
                "default_public_stats": ["5M+ learners served"],
            },
            "style_palette": {"slate": "#2e3a41"},
        },
    )

    client = TestClient(app)
    response = client.get("/api/meta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_public_stats"] == ["5M+ learners served"]
    assert payload["grounding_mode"] == "live"
    assert payload["grounding_warnings"] == ["example warning"]
    assert [item["id"] for item in payload["deliverable_types"]] == [
        "outbound-email",
        "reply-email",
        "sales-collateral",
    ]


def test_workflow_output_budgets_match_current_contract():
    collateral_req = GenerateRequest(asset_type="sales-collateral", objective="Collateral objective")
    reply_req = GenerateRequest(asset_type="reply-email", objective="Reply objective")
    outbound_req = GenerateRequest(asset_type="outbound-email", objective="Outbound objective")

    assert _max_output_tokens(collateral_req) == 1800
    assert _max_output_tokens(reply_req) == 1600
    assert _max_output_tokens(outbound_req) == 1200


def test_proof_sanitizer_rewrites_direct_quotes_in_sales_collateral():
    text = (
        "Headline: Test\n\n"
        "Proof: \"We've standardized on Vocareum for AWS enablement.\" — Jessica Gilmore, Senior Engagement Lead, AWS.\n\n"
        "CTA: Schedule a demo"
    )
    sanitized = _sanitize_proof_sections(text)
    assert '"We' not in sanitized
    assert "Named public proof: Jessica Gilmore, Senior Engagement Lead, AWS" in sanitized
    assert "Use paraphrased proof only." in sanitized


def test_validation_rejects_unapproved_named_proof():
    result = validate_output(
        asset_type="sales-collateral",
        text="Proof: The University of Michigan partnership validates the platform.",
        support_text="Proof: AWS Academy validates the platform.",
        truth_bundle={
            "approved_numeric_claims": [],
            "default_public_stats": [],
            "approved_named_proof": ["AWS Academy"],
            "allowed_reference_names": ["Vocareum"],
        },
        objective_text="Write grounded sales collateral.",
    )

    assert any(issue.code == "disallowed_named_proof" for issue in result.issues)


def test_validation_rejects_partnership_rollout_reference_in_reply():
    result = validate_output(
        asset_type="reply-email",
        text="We have implemented this governed access layer in partnerships such as our campus-wide rollout with the University of Michigan.",
        support_text="AI Gateway provides governed model access.",
        truth_bundle={
            "approved_numeric_claims": [],
            "default_public_stats": [],
            "approved_named_proof": ["AWS Academy"],
            "allowed_reference_names": ["Vocareum", "AI Gateway"],
        },
        objective_text="Reply to this thread.",
    )

    assert any(issue.code == "disallowed_named_proof" for issue in result.issues)


def test_numeric_phrase_extraction_stops_at_sentence_boundary():
    phrases = _extract_numeric_phrases(
        "Vocareum works with 7,000+ institutions and organizations. We help teams govern access."
    )

    assert phrases == ["7,000+ institutions and organizations"]


def test_validation_allows_short_grounded_claim_with_one_meaningful_overlap():
    result = validate_output(
        asset_type="outbound-email",
        text="We help teams govern access.",
        support_text="AI Gateway provides governed model access with policy controls.",
        truth_bundle={
            "approved_numeric_claims": [],
            "default_public_stats": [],
            "approved_named_proof": [],
        },
        objective_text="Write an outbound email about governed model access.",
    )

    assert result.ok
    assert result.issues == []


def test_deliverable_types_match_current_contract():
    assert [item["id"] for item in DELIVERABLE_TYPES] == [
        "outbound-email",
        "reply-email",
        "sales-collateral",
    ]


def test_collateral_examples_do_not_instruct_quotes():
    collateral_examples = [item for item in EXAMPLE_PATTERNS if item["group"] == "collateral"]
    combined = " ".join(
        " ".join(item.get("structure", []) + item.get("claims_to_keep", []))
        for item in collateral_examples
    ).lower()
    assert "quote" not in combined
