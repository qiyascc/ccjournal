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

"""Yayından PDF galley üretimi (WeasyPrint) — düzenlenebilir şablonla.

PDF'in yerleşimi/içeriği `PdfTemplate` (dergi başına, admin'den düzenlenebilir)
ile belirlenir: body_html + css, Django şablon değişkenleriyle. DB'de aktif
şablon yoksa modeldeki varsayılan (DEFAULT_PDF_BODY/CSS) kullanılır.

Render, ana Django motoruyla DEĞİL, izole bir Engine ile yapılır: yalnız
autoescape + temel filtreler; `{% load %}`/keyfi etiketler yüklenmez.
"""
from __future__ import annotations

from html import escape

from django.core.files.base import ContentFile
from django.template import Context, Engine

_PDF_ENGINE = Engine(debug=False, autoescape=True, builtins=[
    "django.template.defaulttags", "django.template.defaultfilters",
])


def _render(src: str, ctx: dict) -> str:
    return _PDF_ENGINE.from_string(src).render(Context(ctx, autoescape=True))


def _context_for(publication, locale=None, *, request=None) -> dict:
    journal = publication.submission.journal
    jt = (journal.translations.filter(locale=journal.primary_locale).first()
          or journal.translations.first())
    journal_title = jt.title if jt else "Journal"

    t = ((publication.translations.filter(locale=locale).first() if locale else None)
         or publication.translations.filter(locale=publication.primary_locale).first()
         or publication.translations.first())

    authors = "; ".join(
        f"{a.given_name} {a.family_name}".strip()
        for a in publication.authors.all()) or "—"
    affil = "<br>".join(sorted({escape(a.affiliation)
                                for a in publication.authors.all() if a.affiliation}))

    issue = publication.issue
    issue_line = ""
    if issue:
        parts = [f"Vol. {issue.volume}" if issue.volume else "",
                 f"No. {issue.number}" if issue.number else "",
                 f"({issue.year})" if issue.year else ""]
        issue_line = " ".join(p for p in parts if p)

    logo_url = ""
    if getattr(journal, "logo", None):
        try:
            url = journal.logo.url
            if request is not None:
                url = request.build_absolute_uri(url)
            logo_url = url
        except Exception:
            logo_url = ""

    return {
        "journal_title": journal_title,
        "title": (t.title if t else "Untitled"),
        "subtitle": (getattr(t, "subtitle", "") if t else ""),
        "abstract": (t.abstract if t and t.abstract else ""),
        "body": (t.body if t and getattr(t, "body", "") else ""),
        "authors": authors,
        "affiliations": affil,
        "doi": (publication.doi.doi if publication.doi_id else ""),
        "issue_line": issue_line,
        "date_published": (publication.date_published.isoformat()
                           if publication.date_published else ""),
        "license_url": (publication.license_url or ""),
        "keywords": ", ".join(k.term for k in publication.keywords.all()[:12]),
        "logo_url": logo_url,
        "volume": (issue.volume if issue else ""),
        "number": (issue.number if issue else ""),
        "year": (issue.year if issue else ""),
    }


def _active_template(journal):
    return journal.pdf_templates.filter(is_active=True).order_by("id").first()


def render_pdf_html(publication, locale=None, *, request=None, template=None) -> tuple[str, str]:
    """(html, page_size) döndürür — önizleme ve üretim ortak kullanır.

    `template` verilirse o PdfTemplate kullanılır (admin'de kaydedilmemiş önizleme için);
    aksi halde derginin aktif şablonu seçilir.
    """
    from .models import DEFAULT_PDF_BODY, DEFAULT_PDF_CSS, DEFAULT_PDF_DESIGN
    journal = publication.submission.journal
    tpl = template if template is not None else _active_template(journal)

    if tpl is None:
        body_src, css_src, page_size = DEFAULT_PDF_BODY, DEFAULT_PDF_CSS, "A4"
    elif getattr(tpl, "mode", "html") == "visual":
        from .pdf_builder import compile_design
        design = tpl.design or DEFAULT_PDF_DESIGN
        body_src, css_src = compile_design(design)
        page_size = (design.get("page", {}) or {}).get("size", "A4")
    else:
        body_src = tpl.body_html or DEFAULT_PDF_BODY
        css_src = tpl.css or DEFAULT_PDF_CSS
        page_size = (tpl.page_size or "A4")

    ctx = _context_for(publication, locale=locale, request=request)
    body = _render(body_src, ctx)
    css = _render(css_src, ctx)
    html = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{css}</style></head><body>{body}</body></html>")
    return html, page_size


def generate_pdf_galley(publication, *, locale=None, label="PDF", approve=True,
                        replace=True, request=None):
    """Aktif PdfTemplate'e göre PDF galley üretir/günceller; Galley döndürür."""
    from weasyprint import HTML
    from apps.submissions.models import FileStage, SubmissionFile
    from .models import Galley

    html, _ = render_pdf_html(publication, locale=locale, request=request)
    pdf_bytes = HTML(string=html).write_pdf()

    t = (publication.translations.filter(locale=publication.primary_locale).first()
         or publication.translations.first())
    base = (t.title[:60] if t and t.title else f"article-{publication.pk}")
    safe = "".join(c if c.isalnum() or c in "- " else "" for c in base).strip().replace(" ", "-")
    fname = f"{safe or 'article'}.pdf"

    sub = publication.submission
    sf = SubmissionFile.objects.create(
        submission=sub, original_filename=fname, mimetype="application/pdf",
        file_stage=FileStage.PROOF, file_size=len(pdf_bytes),
    )
    sf.file.save(f"galley/{publication.pk}-{fname}", ContentFile(pdf_bytes), save=True)

    galley = None
    if replace:
        galley = (publication.galleys.filter(label=label, remote_url="")
                  .order_by("seq").first())
    if galley:
        galley.file = sf
        galley.is_approved = approve
        galley.save(update_fields=["file", "is_approved"])
    else:
        seq = (publication.galleys.count() + 1) * 1.0
        galley = Galley.objects.create(
            publication=publication, label=label, file=sf,
            is_approved=approve, seq=seq, locale=locale or "")
    return galley
