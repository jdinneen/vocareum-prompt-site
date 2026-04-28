from fastapi.testclient import TestClient

from app.examples import DELIVERABLE_TYPES, EXAMPLE_PATTERNS
from app.grounding import SOURCE_TITLE, grounding_block
from app.main import (
    GenerateRequest,
    _build_user_prompt,
    _brief_needs_more_detail,
    _max_output_tokens,
    _auto_quality_report,
    _post_process,
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


def test_grounded_answer_prompt_stays_generic(monkeypatch):
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
        asset_type="grounded-answer",
        objective="Explain AI Gateway for a university CIO in three short paragraphs.",
    )

    prompt = _build_user_prompt(req)

    assert "Workflow: grounded-answer" in prompt
    assert "Do not force email, one-pager, or deck structure" in prompt
    assert "Answer directly from the grounding." in prompt
    assert "No explicit example pattern available." not in prompt


def test_reply_post_process_adds_missing_scheduling_response():
    req = GenerateRequest(
        asset_type="reply-email",
        objective="Thread: Can Vocareum provide ChatGPT access? Also, would next Tuesday at 5:00 PM work for a follow-up?",
    )
    text = (
        "Subject: Re: Follow-up\n\n"
        "Hi [Name],\n\n"
        "Vocareum provides governed API-based access through AI Gateway rather than consumer chatbot seats.\n\n"
        "Best,\nJon"
    )
    processed = _post_process(req, text)
    assert "if next tuesday at 5:00 pm works for you" in processed.lower()
    assert "suggest an alternative" in processed.lower()


def test_brief_check_rejects_thin_outbound_email():
    result = _brief_needs_more_detail(
        GenerateRequest(
            asset_type="outbound-email",
            product="AI Compass",
            objective="email kim majerus",
        )
    )
    assert result is not None
    assert "too thin" in result["message"].lower()


def test_brief_check_rejects_too_short_grounded_answer():
    result = _brief_needs_more_detail(
        GenerateRequest(
            asset_type="grounded-answer",
            objective="AI Gateway",
        )
    )
    assert result is not None
    assert "too thin" in result["message"].lower()


def test_outbound_post_process_adds_goal_based_next_step():
    req = GenerateRequest(
        asset_type="outbound-email",
        objective="Write an outbound email to Kim Majerus about governed model access for students. Goal: ask for a follow-up meeting about AI Gateway.",
    )
    text = (
        "Subject: Governed model access for student AI coursework\n\n"
        "Hi Kim,\n\n"
        "Vocareum AI Gateway provides governed model access for coursework.\n\n"
        "Best,\nJon"
    )
    processed = _post_process(req, text)
    assert "would you be open to a short follow-up meeting next week?" in processed.lower()


def test_validation_allows_time_from_thread_context():
    result = validate_output(
        asset_type="reply-email",
        text="If next Tuesday at 5:00 PM works for you, I am happy to confirm that time.",
        support_text="AI Gateway provides governed model access.",
        truth_bundle={"approved_numeric_claims": [], "default_public_stats": [], "approved_named_proof": [], "allowed_reference_names": ["AI Gateway"]},
        objective_text="Thread: Would next Tuesday at 5:00 PM work for a follow-up?",
    )
    assert result.ok


def test_auto_quality_report_flags_missing_schedule_completion():
    req = GenerateRequest(
        asset_type="reply-email",
        product="AI Gateway",
        objective="Thread: Can Vocareum provide ChatGPT access? Also, would next Tuesday at 5:00 PM work for a follow-up?",
    )
    report = _auto_quality_report(
        req,
        "Subject: Re: Follow-up\n\nVocareum provides governed API-based access through AI Gateway.",
        "AI Gateway provides governed model access.",
        {"approved_numeric_claims": [], "default_public_stats": [], "approved_named_proof": [], "allowed_reference_names": ["AI Gateway"]},
    )
    assert any("scheduling ask" in item.lower() for item in report["blockers"])


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
        "one-pager",
        "sales-deck-brief",
    ]


def test_generate_endpoint_returns_brief_error_for_thin_prompt(monkeypatch):
    monkeypatch.setattr(
        "app.main.load_grounding",
        lambda: {
            "source": {"title": SOURCE_TITLE, "last_reviewed": "2026-04-27", "doc_url": "https://example.com/catalog"},
            "mode": "live",
            "warnings": [],
            "catalog_sections": {"AI Compass": "section"},
            "truth_bundle": {"default_public_stats": []},
            "style_palette": {"slate": "#2e3a41"},
        },
    )
    client = TestClient(app)
    response = client.post(
        "/api/generate",
        json={
            "asset_type": "outbound-email",
            "product": "AI Compass",
            "objective": "email kim majerus",
            "extra_constraints": "",
            "audience": "aws",
        },
    )
    assert response.status_code == 422
    assert "too thin" in response.json()["detail"]["message"].lower()


def test_workflow_output_budgets_match_current_contract():
    grounded_req = GenerateRequest(asset_type="grounded-answer", objective="Grounded objective")
    collateral_req = GenerateRequest(asset_type="sales-collateral", objective="Collateral objective")
    reply_req = GenerateRequest(asset_type="reply-email", objective="Reply objective")
    outbound_req = GenerateRequest(asset_type="outbound-email", objective="Outbound objective")

    assert _max_output_tokens(grounded_req) == 1400
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


def test_post_process_restores_governed_public_stat_strings():
    req = GenerateRequest(asset_type="outbound-email", objective="Outbound objective")
    text = (
        "Vocareum supports over 2 million AWS learners and 7,000 institutions globally. "
        "The platform also serves 5 million total platform learners."
    )

    processed = _post_process(req, text)

    assert "2M+ AWS learners" in processed
    assert "7,000+ institutions and organizations" in processed
    assert "5M+ total platform learners" in processed


def test_deliverable_types_match_current_contract():
    assert [item["id"] for item in DELIVERABLE_TYPES] == [
        "outbound-email",
        "reply-email",
        "sales-collateral",
        "one-pager",
        "sales-deck-brief",
    ]


def test_collateral_examples_do_not_instruct_quotes():
    collateral_examples = [item for item in EXAMPLE_PATTERNS if item["group"] == "collateral"]
    combined = " ".join(
        " ".join(item.get("structure", []) + item.get("claims_to_keep", []))
        for item in collateral_examples
    ).lower()
    assert "quote" not in combined


def test_grounded_answer_allows_paraphrased_product_description():
    """Regression: grounded-answer about On-the-Fly Labs should not fail
    when the model paraphrases catalog language with claim verbs."""
    support_text = (
        "On-the-Fly Labs\n"
        "AI-generated hands-on labs created rapidly for a specific learner, cohort, workshop, or event.\n"
        "AI-assisted lab generation from a learning objective, audience description, and tooling context.\n"
        "Structured output including instructions, starter code or templates, validation criteria, "
        "and environment configuration.\n"
        "Deployable on standard Vocareum infrastructure with full governance controls.\n"
        "Compatible with AI Gateway for labs that require governed model access."
    )
    truth_bundle = {
        "default_public_stats": ["2M+ AWS learners"],
        "approved_named_proof": ["AWS Academy"],
        "approved_numeric_claims": [],
    }
    # Typical LLM paraphrase of catalog content
    output = (
        "On-the-Fly Labs provides AI-assisted generation of hands-on lab environments "
        "tailored to a specific learning objective, cohort, or workshop context. "
        "The platform delivers structured labs including instructions, starter code, "
        "and validation criteria, all deployable on governed Vocareum cloud infrastructure."
    )
    result = validate_output(
        asset_type="grounded-answer",
        text=output,
        support_text=support_text,
        truth_bundle=truth_bundle,
        objective_text="tell me about the vocareum on the fly labs product",
    )
    assert result.ok, f"Unexpected validation issues: {[i.detail for i in result.issues]}"


def test_outbound_email_still_catches_ungrounded_claims():
    """Ensure outbound-email mode still flags sentences with weak grounding overlap."""
    support_text = "On-the-Fly Labs\nAI-generated hands-on labs."
    truth_bundle = {
        "default_public_stats": [],
        "approved_named_proof": [],
        "approved_numeric_claims": [],
    }
    output = (
        "Subject: Exciting news\n\n"
        "Vocareum provides enterprise blockchain orchestration with quantum-ready "
        "containerized microservice federation across hybrid sovereign meshes."
    )
    result = validate_output(
        asset_type="outbound-email",
        text=output,
        support_text=support_text,
        truth_bundle=truth_bundle,
        objective_text="write an email about blockchain",
    )
    assert not result.ok
    assert any(issue.code == "claims_not_in_grounding" for issue in result.issues)
