from fastapi.testclient import TestClient

from app.grounding import SOURCE_TITLE, grounding_block
from app.main import GenerateRequest, _build_user_prompt, app
from app.renderers import parse_deck_text


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
            "default_public_stats": [],
            "contextual_stats": [],
            "style_palette": {},
        },
    )
    req = GenerateRequest(
        asset_type="one-pager",
        audience="AWS solutions architects",
        objective="Create an On-the-Fly Labs one-pager for AWS workshop teams.",
        extra_constraints="Use grounded proof only.",
        example_pattern="aws-cosell-one-pager",
    )

    prompt = _build_user_prompt(req)

    assert "Relevant live product catalog sections:" in prompt
    assert "Example Collateral: Vocareum_On_the_Fly_Labs_AWS_Co_Sell.pdf" in prompt
    assert "AWS collateral example excerpt" in prompt


def test_grounding_block_uses_catalog_title(monkeypatch):
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
            "catalog_sections": {},
            "email_sections": {},
            "collateral_examples": {},
            "default_public_stats": ["5M+ learners served"],
            "contextual_stats": [],
            "style_palette": {},
        },
    )

    prompt = grounding_block("general overview")

    assert f"Document: {SOURCE_TITLE}" in prompt
    assert "README / Doc Rules" not in prompt


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
            "default_public_stats": ["5M+ learners served"],
            "style_palette": {"slate": "#2e3a41"},
        },
    )

    client = TestClient(app)
    response = client.get("/api/meta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["public_stats"] == ["5M+ learners served"]
    assert payload["grounding_mode"] == "live"
    assert payload["grounding_warnings"] == ["example warning"]
