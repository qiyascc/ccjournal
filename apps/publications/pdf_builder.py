# ==========================================================
#
# █▀█ █ █▄█ ▄▀█ █▀  █▀▀ █▀▀
# ▀▀█ █ ░█░ █▀█ ▄█  █▄▄ █▄▄
#
# Project     : CC Journal
# Developed by: Qiyas CC
# Copyright © 2026 Qiyas CC
# All Rights Reserved.
# ==========================================================

"""Görsel tasarım (JSON) → PDF HTML+CSS derleyici.

PdfTemplate.mode == 'visual' olduğunda, `design` sözlüğünden makale gövdesi
ve sayfa CSS'i üretilir. Kod gerektirmez: renk/​font/​logo/​bölüm sırası ayarları
buradan somut HTML+CSS'e dönüşür. Üretilen çıktı yine `{{ değişken }}` içerir;
asıl doldurma render anında izole şablon motoruyla yapılır (pdf.py).
"""
from __future__ import annotations

from html import escape

_FONT_STACK = {
    "sans": "'DejaVu Sans', Arial, sans-serif",
    "serif": "'DejaVu Serif', Georgia, serif",
}

_SECTION_HTML = {
    "brand": (
        '<header class="cc-brandrow">'
        '{logo}'
        '<div class="cc-brandtext"><div class="cc-jname">{{{{ journal_title }}}}</div>'
        '{{% if issue_line %}}<div class="cc-issue">{{{{ issue_line }}}}</div>{{% endif %}}'
        '</div></header>'
    ),
    "badge": '{{% if true %}}<div class="cc-badge">{badge_text}</div>{{% endif %}}',
    "title": '<h1 class="cc-title">{{ title }}</h1>',
    "subtitle": '{% if subtitle %}<p class="cc-subtitle">{{ subtitle }}</p>{% endif %}',
    "authors": '<p class="cc-authors">{{ authors }}</p>',
    "affiliations": '{% if affiliations %}<p class="cc-affil">{{ affiliations|safe }}</p>{% endif %}',
    "meta": (
        '<div class="cc-meta">'
        '{% if doi %}DOI: <a href="https://doi.org/{{ doi }}">{{ doi }}</a>{% endif %}'
        '{% if date_published %} &middot; {{ date_published }}{% endif %}'
        '{% if license_url %} &middot; <a href="{{ license_url }}">License</a>{% endif %}'
        '</div>'
    ),
    "abstract": '{% if abstract %}<h2 class="cc-h2">Abstract</h2><div class="cc-abstract">{{ abstract }}</div>{% endif %}',
    "keywords": '{% if keywords %}<p class="cc-kw"><strong>Keywords:</strong> {{ keywords }}</p>{% endif %}',
    "body": '{% if body %}<hr class="cc-sep"><div class="cc-body">{{ body|safe }}</div>{% endif %}',
}


def _logo_html(design) -> str:
    logo = design.get("logo", {})
    if not logo.get("show", True) or logo.get("position") == "hidden":
        return ""
    return '{% if logo_url %}<img class="cc-logo" src="{{ logo_url }}" alt="">{% endif %}'


def build_body_html(design: dict) -> str:
    sections = design.get("sections") or []
    badge = design.get("badge", {})
    parts = ["<article>"]
    for sec in sections:
        if not sec.get("show", True):
            continue
        sid = sec.get("id")
        if sid == "badge":
            if not badge.get("show"):
                continue
            parts.append(f'<div class="cc-badge">{escape(badge.get("text","") or "")}</div>')
            continue
        tpl = _SECTION_HTML.get(sid)
        if not tpl:
            continue
        if sid == "brand":
            parts.append(tpl.format(logo=_logo_html(design)))
        else:
            parts.append(tpl)
    parts.append("</article>")
    return "\n".join(parts)


def build_css(design: dict) -> str:
    c = {**{"accent": "#1f3df2", "accent2": "#3de8c0", "text": "#1a1a1a",
            "muted_text": "#555555", "bg": "#ffffff", "panel": "#f5f5f3",
            "rule": "#1f3df2"}, **(design.get("colors") or {})}
    fonts = design.get("fonts") or {}
    head = _FONT_STACK.get(fonts.get("heading", "sans"), _FONT_STACK["sans"])
    body = _FONT_STACK.get(fonts.get("body", "serif"), _FONT_STACK["serif"])
    page = design.get("page") or {}
    size = page.get("size", "A4")
    mt = page.get("margin_top", 2.4); mx = page.get("margin_x", 2.0)
    mb = page.get("margin_bottom", 2.4)
    logo = design.get("logo", {})
    logo_size = int(logo.get("size", 44) or 44)
    pos = logo.get("position", "left")
    rule = design.get("rule", {})
    rule_w = int(rule.get("width", 2) or 2) if rule.get("show", True) else 0
    badge = design.get("badge", {})

    footer = page.get("footer", "") or ""
    footer_css = (f'@bottom-center {{ content: "{footer}"; font-size: 8pt; color: #999; }}'
                  if footer else "")
    if page.get("page_numbers"):
        footer_css += ('@bottom-right { content: counter(page) " / " counter(pages);'
                       ' font-size: 8pt; color: #aaa; }')

    brand_justify = {"left": "flex-start", "center": "center",
                     "right": "space-between"}.get(pos, "flex-start")
    logo_order = "order:2;" if pos == "right" else ""

    return f"""
@page {{ size: {size}; margin: {mt}cm {mx}cm {mb}cm; {footer_css} }}
body {{ font-family: {body}; color: {c['text']}; font-size: 10.5pt; line-height: 1.55; }}
.cc-brandrow {{ display: flex; align-items: center; gap: 12px; justify-content: {brand_justify};
  {'border-bottom: ' + str(rule_w) + 'px solid ' + c['rule'] + ';' if rule_w else ''}
  padding-bottom: 8px; margin-bottom: 18px; }}
.cc-logo {{ height: {logo_size}px; width: auto; {logo_order} }}
.cc-brandtext {{ {'order:1;' if pos == 'right' else ''} }}
.cc-jname {{ font-family: {head}; font-weight: bold; font-size: 11pt;
  letter-spacing: .04em; text-transform: uppercase; color: {c['accent']}; }}
.cc-issue {{ font-family: {head}; font-size: 8pt; color: {c['muted_text']}; letter-spacing: .04em; }}
.cc-badge {{ display: inline-block; background: {badge.get('color', c['accent'])}; color: #fff;
  font-family: {head}; font-weight: bold; font-size: 7.5pt; letter-spacing: .14em;
  padding: 3px 10px; border-radius: 3px; margin-bottom: 12px; }}
.cc-title {{ font-family: {head}; font-size: 20pt; line-height: 1.18; margin: 0 0 6px; color: {c['text']}; }}
.cc-subtitle {{ font-size: 12pt; font-style: italic; color: {c['muted_text']}; margin: 0 0 12px; }}
.cc-authors {{ font-family: {head}; font-size: 11pt; font-weight: 600; margin: 0 0 3px; }}
.cc-affil {{ font-size: 9pt; color: {c['muted_text']}; margin: 0 0 14px; }}
.cc-meta {{ font-family: {head}; font-size: 8.5pt; color: {c['muted_text']};
  background: {c['panel']}; padding: 8px 12px; border-radius: 6px; margin-bottom: 18px; }}
.cc-meta a {{ color: {c['accent']}; text-decoration: none; }}
.cc-h2 {{ font-family: {head}; font-size: 10pt; text-transform: uppercase;
  letter-spacing: .06em; color: {c['muted_text']}; margin: 18px 0 6px; }}
.cc-abstract {{ text-align: justify; }}
.cc-kw {{ font-size: 9pt; color: {c['muted_text']}; margin-top: 12px; }}
.cc-sep {{ border: none; border-top: 1px solid #ddd; margin: 22px 0; }}
.cc-body {{ text-align: justify; }}
.cc-body h2 {{ font-family: {head}; font-size: 12pt; color: {c['accent']}; margin: 18px 0 6px; }}
.cc-body h3 {{ font-family: {head}; font-size: 10.5pt; margin: 14px 0 5px; }}
.cc-body p {{ margin: 0 0 9px; }}
.cc-body ul, .cc-body ol {{ margin: 6px 0 12px 18px; }}
.cc-body li {{ margin-bottom: 4px; }}
.cc-body blockquote {{ border-left: 3px solid {c['accent2']}; margin: 10px 0; padding-left: 12px;
  color: {c['muted_text']}; }}
.cc-body img {{ max-width: 100%; }}
.cc-body .cc-table-wrap {{ margin: 10px 0; }}
.cc-body table.cc-table {{ border-collapse: collapse; width: 100%; font-size: 9pt; }}
.cc-body table.cc-table th, .cc-body table.cc-table td {{
  border: 0.5pt solid {c['muted_text']}; padding: 4px 6px; text-align: left; vertical-align: top; }}
.cc-body table.cc-table th {{ background: {c['panel']}; font-weight: bold; }}
""".strip()


def compile_design(design: dict) -> tuple[str, str]:
    """(body_html, css) — görsel tasarımdan derlenmiş çıktı."""
    return build_body_html(design), build_css(design)
