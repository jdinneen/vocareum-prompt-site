from __future__ import annotations

import html
import re
from typing import Any


ONE_PAGER_SECTIONS = [
    "Headline",
    "Subhead",
    "Stat Bar",
    "Problem",
    "How It Works",
    "Who Uses This",
    "Proof",
    "CTA",
]
OVERVIEW_SECTIONS = [
    "Headline",
    "Subhead",
    "Core Capabilities",
    "Best-Fit Buyers",
    "Proof",
    "CTA",
]


def _normalize_line_breaks(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _extract_labeled_sections(text: str, labels: list[str]) -> dict[str, str]:
    cleaned = _normalize_line_breaks(text)
    pattern = re.compile(
        r"(?ms)^(?:[#>*\-\s]*)?(?:\*\*)?(" + "|".join(re.escape(label) for label in labels) + r")(?:\*\*)?(?::)?\s*(.*?)\s*(?=^(?:[#>*\-\s]*)?(?:\*\*)?(?:"
        + "|".join(re.escape(label) for label in labels)
        + r")(?:\*\*)?(?::)?\s*|\Z)"
    )
    sections: dict[str, str] = {}
    for match in pattern.finditer(cleaned):
        sections[match.group(1)] = match.group(2).strip()
    return sections


def _split_stat_bar(text: str) -> list[dict[str, str]]:
    normalized = _normalize_line_breaks(text)
    normalized = re.sub(r"(?m)^\s*[-*]\s*", "", normalized)
    raw_parts = [
        part.strip(" .")
        for part in re.split(r"\s*(?:;|\||\n)\s*", normalized)
        if part.strip()
    ]
    items: list[dict[str, str]] = []
    for part in raw_parts[:4]:
        value = part
        label = ""
        if ":" in part:
            value, label = [piece.strip() for piece in part.split(":", 1)]
        elif " - " in part:
            value, label = [piece.strip() for piece in part.split(" - ", 1)]
        else:
            pieces = part.split(" ", 1)
            value = pieces[0].strip()
            label = pieces[1].strip() if len(pieces) > 1 else ""
        items.append({"value": value, "label": label})
    return items


def _split_numbered_steps(text: str) -> list[dict[str, str]]:
    normalized = _normalize_line_breaks(text)
    normalized = re.sub(r"\s+(?=\d+\.\s+)", "\n", normalized)
    matches = re.findall(r"(?:^|\n)\s*(\d+)\.\s+(.*?)(?=(?:\n\s*\d+\.\s+)|\Z)", normalized, re.S)
    steps: list[dict[str, str]] = []
    for number, body in matches:
        body = " ".join(body.strip().split())
        if ". " in body:
            title, detail = body.split(".", 1)
            steps.append({"number": number, "title": title.strip(), "detail": detail.strip()})
        else:
            steps.append({"number": number, "title": body.rstrip(".").strip(), "detail": ""})
    return steps


def _split_people(text: str) -> list[str]:
    if "\n" in text:
        return [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    return [part.strip() for part in re.split(r"\s*,\s*", text) if part.strip()]


def _paragraphs(text: str) -> list[str]:
    return [line.strip() for line in text.split("\n") if line.strip()]


def _split_bullets_or_lines(text: str) -> list[str]:
    normalized = _normalize_line_breaks(text)
    normalized = re.sub(r"(?m)^\s*[-*]\s*", "", normalized)
    if "\n" in normalized:
        return [line.strip() for line in normalized.splitlines() if line.strip()]
    return [part.strip() for part in re.split(r"\s*;\s*", normalized) if part.strip()]


def _split_slides(text: str) -> list[dict[str, Any]]:
    cleaned = _normalize_line_breaks(text)
    pattern = re.compile(
        r"(?ms)^Slide\s+(\d+):\s*(.*?)\s*(?=^Slide\s+\d+:\s*|\Z)"
    )
    slides: list[dict[str, Any]] = []
    for match in pattern.finditer(cleaned):
        number = match.group(1)
        body = match.group(2).strip()
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        title = lines[0] if lines else ""
        bullets = []
        for line in lines[1:]:
            bullets.append(re.sub(r"^\s*[*-]\s*", "", line).strip())
        if not bullets and len(lines) > 1:
            bullets = lines[1:]
        slides.append({"number": number, "title": title, "bullets": [b for b in bullets if b]})
    return slides


def parse_one_pager_text(text: str) -> dict[str, Any] | None:
    sections = _extract_labeled_sections(text, ONE_PAGER_SECTIONS)
    if not {"Headline", "Subhead", "Problem", "How It Works", "Proof", "CTA"}.issubset(sections):
        return None
    return {
        "headline": sections.get("Headline", ""),
        "subhead": sections.get("Subhead", ""),
        "stats": _split_stat_bar(sections.get("Stat Bar", "")),
        "problem": _paragraphs(sections.get("Problem", "")),
        "steps": _split_numbered_steps(sections.get("How It Works", "")),
        "who_uses": _split_people(sections.get("Who Uses This", "")),
        "proof": _paragraphs(sections.get("Proof", "")),
        "cta": sections.get("CTA", ""),
    }


def parse_overview_text(text: str) -> dict[str, Any] | None:
    sections = _extract_labeled_sections(text, OVERVIEW_SECTIONS)
    if not {"Headline", "Subhead", "Core Capabilities", "Best-Fit Buyers", "Proof", "CTA"}.issubset(sections):
        return None
    return {
        "headline": sections.get("Headline", ""),
        "subhead": sections.get("Subhead", ""),
        "capabilities": _split_bullets_or_lines(sections.get("Core Capabilities", "")),
        "buyers": _split_bullets_or_lines(sections.get("Best-Fit Buyers", "")),
        "proof": _paragraphs(sections.get("Proof", "")),
        "cta": sections.get("CTA", ""),
    }


def parse_deck_text(text: str) -> dict[str, Any] | None:
    slides = _split_slides(text)
    if len(slides) != 6:
        return None
    return {"slides": slides}


def render_one_pager_html(payload: dict[str, Any]) -> str:
    headline = html.escape(payload["headline"])
    subhead = html.escape(payload["subhead"])
    cta = html.escape(payload["cta"])

    stats_html = "".join(
        f"""
        <div class="stat-item">
          <div class="stat-num">{html.escape(item['value'])}</div>
          <div class="stat-label">{html.escape(item['label'])}</div>
        </div>
        """
        for item in payload["stats"]
    ) or """
        <div class="stat-item">
          <div class="stat-num">Grounded</div>
          <div class="stat-label">Product copy only</div>
        </div>
    """

    problem_html = "".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in payload["problem"])
    steps_html = "".join(
        f"""
        <div class="step">
          <div class="step-num">{html.escape(step['number'])}</div>
          <div class="step-text">
            {f"<strong>{html.escape(step['title'])}.</strong> " if step['title'] else ""}
            {html.escape(step['detail'])}
          </div>
        </div>
        """
        for step in payload["steps"]
    )
    who_uses_html = "".join(f"<li>{html.escape(item)}</li>" for item in payload["who_uses"])
    proof_html = "".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in payload["proof"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{headline}</title>
  <style>
    :root {{
      --slate: #2e3a41;
      --steel: #445664;
      --powder: #c1d3dd;
      --coral: #ff7f50;
      --gray: #efefef;
      --white: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #f5f2ec;
      font-family: "Manrope", "Helvetica Neue", Arial, sans-serif;
      color: #111111;
    }}
    .sheet {{
      width: min(1100px, calc(100vw - 32px));
      margin: 24px auto;
      background: var(--white);
      box-shadow: 0 28px 70px rgba(46, 58, 65, 0.12);
    }}
    .hero {{
      background: var(--slate);
      color: var(--white);
      padding: 28px 38px 22px;
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 10px;
    }}
    .hero-brand {{
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--powder);
    }}
    .hero-badge {{
      background: var(--coral);
      color: var(--white);
      font-size: 0.72rem;
      font-weight: 800;
      text-transform: uppercase;
      padding: 6px 10px;
      border-radius: 999px;
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: clamp(2rem, 4vw, 3rem);
      line-height: 1;
      letter-spacing: -0.04em;
    }}
    .hero-sub {{
      max-width: 880px;
      font-size: 1rem;
      line-height: 1.55;
      color: var(--powder);
    }}
    .stat-bar {{
      background: var(--steel);
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1px;
    }}
    .stat-item {{
      padding: 16px 18px;
      text-align: center;
      color: var(--white);
    }}
    .stat-num {{
      font-size: 1.7rem;
      font-weight: 800;
      color: var(--coral);
      line-height: 1;
    }}
    .stat-label {{
      margin-top: 6px;
      font-size: 0.74rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--powder);
    }}
    .content {{
      padding: 24px 38px 16px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.08fr) minmax(280px, 0.92fr);
      gap: 28px;
    }}
    .section-head {{
      margin: 0 0 10px;
      padding-bottom: 6px;
      border-bottom: 2px solid var(--powder);
      color: var(--slate);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 0.78rem;
      font-weight: 800;
    }}
    p {{
      margin: 0 0 10px;
      line-height: 1.58;
      font-size: 0.95rem;
    }}
    .step {{
      display: flex;
      gap: 12px;
      margin-bottom: 10px;
      align-items: flex-start;
    }}
    .step-num {{
      width: 24px;
      height: 24px;
      flex-shrink: 0;
      border-radius: 999px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--coral);
      color: var(--white);
      font-size: 0.8rem;
      font-weight: 800;
    }}
    .step-text {{
      line-height: 1.55;
      font-size: 0.93rem;
    }}
    .step-text strong {{
      color: var(--slate);
    }}
    .people-box {{
      background: rgba(193, 211, 221, 0.28);
      border-left: 4px solid var(--coral);
      padding: 14px 16px;
    }}
    .people-box ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .people-box li {{
      margin-bottom: 8px;
      line-height: 1.45;
    }}
    .proof-block {{
      margin-top: 18px;
      padding: 16px 18px;
      background: var(--slate);
      color: var(--white);
      border-radius: 16px;
    }}
    .proof-block p {{
      color: #edf4f7;
      margin-bottom: 8px;
    }}
    .cta-bar {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-top: 22px;
      padding-top: 16px;
      border-top: 1px solid rgba(68, 86, 100, 0.18);
    }}
    .cta-label {{
      font-size: 0.75rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--steel);
    }}
    .cta-copy {{
      font-size: 0.98rem;
      color: var(--slate);
      line-height: 1.55;
      max-width: 760px;
    }}
    .footer {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 38px 24px;
      color: var(--steel);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    @media (max-width: 900px) {{
      .sheet {{
        width: calc(100vw - 20px);
      }}
      .grid {{
        grid-template-columns: 1fr;
      }}
      .hero,
      .content,
      .footer {{
        padding-left: 20px;
        padding-right: 20px;
      }}
      .cta-bar {{
        flex-direction: column;
        align-items: flex-start;
      }}
    }}
  </style>
</head>
<body>
  <main class="sheet">
    <section class="hero">
      <div class="hero-top">
        <div class="hero-brand">Vocareum</div>
        <div class="hero-badge">Experimental Preview</div>
      </div>
      <h1>{headline}</h1>
      <div class="hero-sub">{subhead}</div>
    </section>

    <section class="stat-bar">{stats_html}</section>

    <section class="content">
      <div class="grid">
        <div>
          <h2 class="section-head">The Problem</h2>
          {problem_html}

          <h2 class="section-head">How It Works</h2>
          {steps_html}
        </div>

        <div>
          <h2 class="section-head">Who Uses This</h2>
          <div class="people-box">
            <ul>{who_uses_html}</ul>
          </div>

          <div class="proof-block">
            <h2 class="section-head" style="border-bottom-color: rgba(255,255,255,0.14); color: #ffffff;">Proof</h2>
            {proof_html}
          </div>
        </div>
      </div>

      <div class="cta-bar">
        <div class="cta-label">Call To Action</div>
        <div class="cta-copy">{cta}</div>
      </div>
    </section>

    <footer class="footer">
      <span>vocareum.com</span>
      <span>experimental preview</span>
    </footer>
  </main>
</body>
</html>
"""


def render_overview_html(payload: dict[str, Any]) -> str:
    headline = html.escape(payload["headline"])
    subhead = html.escape(payload["subhead"])
    capabilities_html = "".join(f"<li>{html.escape(item)}</li>" for item in payload["capabilities"])
    buyers_html = "".join(f"<li>{html.escape(item)}</li>" for item in payload["buyers"])
    proof_html = "".join(f"<p>{html.escape(item)}</p>" for item in payload["proof"])
    cta = html.escape(payload["cta"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{headline}</title>
  <style>
    :root {{ --slate:#2e3a41; --steel:#445664; --powder:#c1d3dd; --coral:#ff7f50; --white:#ffffff; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#f2efe8; font-family:"Manrope","Helvetica Neue",Arial,sans-serif; color:#111; }}
    .canvas {{ width:min(1180px, calc(100vw - 32px)); margin:24px auto; background:#fff; box-shadow:0 26px 70px rgba(46,58,65,.12); }}
    .hero {{ padding:34px 38px 24px; background:linear-gradient(135deg,#2e3a41 0%, #445664 100%); color:#fff; }}
    .eyebrow {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.18em; color:#c1d3dd; font-weight:800; }}
    h1 {{ margin:10px 0 12px; font-size:clamp(2.3rem,5vw,3.7rem); line-height:.96; letter-spacing:-.05em; }}
    .subhead {{ max-width:860px; font-size:1.02rem; line-height:1.6; color:#edf5f7; }}
    .body {{ display:grid; grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr); gap:26px; padding:26px 38px; }}
    .block {{ border-radius:18px; padding:18px 20px; background:#f8f9f9; border:1px solid rgba(68,86,100,.12); }}
    .block h2 {{ margin:0 0 12px; font-size:.82rem; text-transform:uppercase; letter-spacing:.14em; color:#445664; }}
    ul {{ margin:0; padding-left:18px; }}
    li {{ margin-bottom:10px; line-height:1.5; }}
    .proof {{ background:#2e3a41; color:#fff; }}
    .proof h2 {{ color:#c1d3dd; }}
    .proof p {{ margin:0 0 10px; line-height:1.58; color:#edf5f7; }}
    .cta {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; padding:0 38px 30px; }}
    .cta-tag {{ padding:8px 12px; border-radius:999px; background:#ff7f50; color:#fff; font-size:.78rem; font-weight:800; text-transform:uppercase; letter-spacing:.12em; }}
    .cta-copy {{ font-size:1rem; line-height:1.6; color:#2e3a41; max-width:860px; }}
    @media (max-width:900px) {{ .canvas {{ width:calc(100vw - 20px); }} .body {{ grid-template-columns:1fr; padding:20px; }} .hero, .cta {{ padding-left:20px; padding-right:20px; }} .cta {{ flex-direction:column; }} }}
  </style>
</head>
<body>
  <main class="canvas">
    <section class="hero">
      <div class="eyebrow">Vocareum overview collateral</div>
      <h1>{headline}</h1>
      <div class="subhead">{subhead}</div>
    </section>
    <section class="body">
      <div class="block">
        <h2>Core Capabilities</h2>
        <ul>{capabilities_html}</ul>
      </div>
      <div class="block">
        <h2>Best-Fit Buyers</h2>
        <ul>{buyers_html}</ul>
      </div>
      <div class="block proof" style="grid-column:1 / -1;">
        <h2>Proof</h2>
        {proof_html}
      </div>
    </section>
    <section class="cta">
      <div class="cta-tag">CTA</div>
      <div class="cta-copy">{cta}</div>
    </section>
  </main>
</body>
</html>"""


def render_deck_html(payload: dict[str, Any]) -> str:
    slides_html = "".join(
        f"""
        <section class="slide">
          <div class="slide-number">Slide {html.escape(slide['number'])}</div>
          <h2>{html.escape(slide['title'])}</h2>
          <ul>{''.join(f'<li>{html.escape(item)}</li>' for item in slide['bullets'])}</ul>
        </section>
        """
        for slide in payload["slides"]
    )
    first_title = payload["slides"][0]["title"] if payload["slides"] else "Rendered deck"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(first_title)}</title>
  <style>
    :root {{ --slate:#2e3a41; --steel:#445664; --powder:#c1d3dd; --coral:#ff7f50; --white:#ffffff; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#ece7df; font-family:"Manrope","Helvetica Neue",Arial,sans-serif; color:#111; }}
    .deck {{ width:min(1320px, calc(100vw - 32px)); margin:22px auto; display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:18px; }}
    .slide {{ min-height:360px; background:#fff; border:1px solid rgba(68,86,100,.12); border-radius:24px; padding:22px; box-shadow:0 22px 60px rgba(46,58,65,.1); position:relative; overflow:hidden; }}
    .slide::before {{ content:''; position:absolute; inset:0 auto auto 0; width:100%; height:10px; background:linear-gradient(90deg,#ff7f50 0%, #c1d3dd 100%); }}
    .slide-number {{ margin-top:8px; font-size:.75rem; font-weight:800; text-transform:uppercase; letter-spacing:.14em; color:#445664; }}
    h2 {{ margin:14px 0 14px; font-size:1.55rem; line-height:1.06; color:#2e3a41; letter-spacing:-.03em; }}
    ul {{ margin:0; padding-left:18px; }}
    li {{ margin-bottom:12px; line-height:1.52; }}
    @media (max-width:720px) {{ .deck {{ width:calc(100vw - 20px); grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main class="deck">{slides_html}</main>
</body>
</html>"""


def render_collateral(asset_type: str, output: str) -> dict[str, Any] | None:
    if asset_type == "one-pager":
        payload = parse_one_pager_text(output)
        if not payload:
            return None
        return {
            "mode": "html",
            "kind": "one-pager",
            "title": payload["headline"],
            "html": render_one_pager_html(payload),
        }
    if asset_type in {"overview-collateral", "sales-collateral"}:
        payload = parse_overview_text(output)
        if not payload:
            return None
        return {
            "mode": "html",
            "kind": asset_type,
            "title": payload["headline"],
            "html": render_overview_html(payload),
        }
    if asset_type == "sales-deck-brief":
        payload = parse_deck_text(output)
        if not payload:
            return None
        return {
            "mode": "html",
            "kind": "sales-deck-brief",
            "title": payload["slides"][0]["title"] if payload["slides"] else "Rendered deck",
            "html": render_deck_html(payload),
        }
    return None
