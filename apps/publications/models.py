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

"""
Yayın (Publication) katmanı = sürümlenmiş, yayımlanabilir metadata.

Burası OJS'i metadata kalitesinde GEÇTİĞİMİZ yer:
  * CRediT katkı taksonomisi (yapısal, standart) — OJS'te yok/zayıf
  * Yapısal kaynakça (Citation) — DOI ile eşlenebilir
  * Fon bilgisi (Funding) — funder ROR/DOI + award no (Crossref/OpenAIRE uyumlu)
  * Anahtar kelime/konu/disiplin -> ayrı, indekslenebilir tablolar (virgülle birleşik string değil)
  * Çevrilebilir metinler -> temiz translation tablosu (EAV değil)
"""
from __future__ import annotations

from django.db import models
from django_countries.fields import CountryField

from apps.core.models import TimeStampedModel, TranslatableMixin, validate_orcid, validate_ror


class VersionStage(models.TextChoices):
    SUBMITTED = "SM", "Submitted Manuscript"
    ACCEPTED = "AM", "Accepted Manuscript"
    PROOF = "PF", "Proof / Final author version"
    RECORD = "VoR", "Version of Record"


class PublicationStatus(models.IntegerChoices):
    QUEUED = 1, "Queued"
    PUBLISHED = 3, "Published"
    DECLINED = 4, "Declined"
    SCHEDULED = 5, "Scheduled"


class Publication(TimeStampedModel, TranslatableMixin):
    submission = models.ForeignKey(
        "submissions.Submission", on_delete=models.CASCADE, related_name="publications"
    )
    primary_locale = models.CharField(max_length=14, default="az")

    section = models.ForeignKey(
        "journals.Section", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="publications",
    )
    issue = models.ForeignKey(
        "journals.Issue", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="publications",
    )
    seq = models.FloatField(default=0.0, help_text="Order in issue table of contents")
    pages = models.CharField(max_length=40, blank=True, help_text="e.g. 12-28")

    version_major = models.PositiveIntegerField(default=1)
    version_minor = models.PositiveIntegerField(default=0)
    version_stage = models.CharField(
        max_length=3, choices=VersionStage.choices, default=VersionStage.RECORD
    )
    source_publication = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="derived_versions"
    )

    status = models.IntegerField(
        choices=PublicationStatus.choices, default=PublicationStatus.QUEUED, db_index=True
    )
    date_published = models.DateField(null=True, blank=True)
    url_path = models.SlugField(max_length=64, blank=True)

    primary_contact = models.ForeignKey(
        "publications.Author", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    doi = models.OneToOneField(
        "core.Doi", null=True, blank=True, on_delete=models.SET_NULL, related_name="publication"
    )

    license_url = models.URLField(blank=True)
    copyright_holder = models.CharField(max_length=255, blank=True)
    copyright_year = models.PositiveIntegerField(null=True, blank=True)

    retracted_at = models.DateField(
        null=True, blank=True,
        help_text="Set to mark this version retracted; a notice banner appears "
                  "on the article page (the article stays readable, per COPE)")
    retraction_note = models.TextField(
        blank=True, help_text="Public retraction/erratum statement shown in the banner")

    data_availability = models.TextField(
        blank=True, help_text="Data/code availability statement (shown on the "
                              "article page; link a Zenodo/OSF DOI if any)")
    ai_statement = models.TextField(
        blank=True, help_text="Declared use of AI tools in this work")
    cited_by_count = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Open citation count (OpenCitations); refreshed by a periodic job")
    cited_by_fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Publication (Version)"
        verbose_name_plural = "Publications (Versions)"
        ordering = ["seq"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "version_major", "version_minor", "version_stage"],
                name="unique_version_per_submission",
            )
        ]

    def __str__(self) -> str:
        return f"{self.tr_value('title') or '(untitled)'} v{self.version_label}"

    @property
    def version_label(self) -> str:
        return f"{self.version_major}.{self.version_minor} {self.version_stage}"

    @property
    def is_published(self) -> bool:
        return self.status == PublicationStatus.PUBLISHED


class PublicationTranslation(models.Model):
    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="translations"
    )
    locale = models.CharField(max_length=14)
    prefix = models.CharField(max_length=64, blank=True, help_text="e.g. 'The'")
    title = models.CharField(max_length=512)
    subtitle = models.CharField(max_length=512, blank=True)
    abstract = models.TextField(blank=True)
    body = models.TextField(blank=True, help_text="Full-text HTML (optional). "
                            "Used for the on-site reader and the generated PDF galley.")
    plain_language_summary = models.TextField(blank=True)
    coverage = models.CharField(max_length=255, blank=True)
    rights = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("publication", "locale")
        verbose_name = "Publication Translation"

    def __str__(self) -> str:
        return f"{self.title} [{self.locale}]"


class CreditRole(models.TextChoices):
    """CRediT taksonomisi — https://credit.niso.org (yapısal katkı rolleri)."""

    CONCEPTUALIZATION = "conceptualization", "Conceptualization"
    DATA_CURATION = "data_curation", "Data curation"
    FORMAL_ANALYSIS = "formal_analysis", "Formal analysis"
    FUNDING = "funding_acquisition", "Funding acquisition"
    INVESTIGATION = "investigation", "Investigation"
    METHODOLOGY = "methodology", "Methodology"
    PROJECT_ADMIN = "project_administration", "Project administration"
    RESOURCES = "resources", "Resources"
    SOFTWARE = "software", "Software"
    SUPERVISION = "supervision", "Supervision"
    VALIDATION = "validation", "Validation"
    VISUALIZATION = "visualization", "Visualization"
    WRITING_ORIGINAL = "writing_original", "Writing - original draft"
    WRITING_REVIEW = "writing_review", "Writing - review & editing"


def _author_access_token():
    import secrets
    return secrets.token_urlsafe(24)


class Author(TimeStampedModel):
    """
    Yayın sürümüne bağlı katkıcı. Sürümlenir (her Publication kendi yazar listesini
    taşır) — böylece bir makalenin tarihçesinde yazar değişiklikleri korunur.
    """

    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="authors"
    )
    given_name = models.CharField(max_length=150)
    family_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)

    orcid = models.CharField(max_length=19, blank=True, validators=[validate_orcid])
    affiliation = models.CharField(max_length=255, blank=True)
    affiliation_ror = models.CharField(max_length=64, blank=True, validators=[validate_ror])
    country = CountryField(blank=True)
    biography = models.TextField(blank=True)

    credit_roles = models.JSONField(
        default=list, blank=True, help_text="List of CreditRole values"
    )
    access_token = models.CharField(max_length=48, db_index=True, editable=False,
                                    default=_author_access_token)
    credit_approved_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Yazar kendi CRediT katkısını bu tarihte onayladı")
    seq = models.FloatField(default=0.0)
    include_in_browse = models.BooleanField(default=True)

    class Meta:
        ordering = ["seq"]
        verbose_name = "Author"
        verbose_name_plural = "Authors"

    def __str__(self) -> str:
        return f"{self.given_name} {self.family_name}".strip()


class Keyword(models.Model):
    """Per-locale keyword as its own row -> indexable/queryable."""

    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="keywords"
    )
    locale = models.CharField(max_length=14)
    term = models.CharField(max_length=120)
    seq = models.FloatField(default=0.0)

    class Meta:
        ordering = ["seq"]
        indexes = [models.Index(fields=["term"])]


class Subject(models.Model):
    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="subjects"
    )
    locale = models.CharField(max_length=14)
    term = models.CharField(max_length=160)


class Citation(models.Model):
    """Structured reference: raw text + optional DOI/parsed fields."""

    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="citations"
    )
    seq = models.PositiveIntegerField(default=0)
    raw = models.TextField(help_text="Raw reference text")
    doi = models.CharField(max_length=255, blank=True)
    structured = models.JSONField(
        default=dict, blank=True, help_text="Parsed fields (author, year, journal...)"
    )

    class Meta:
        ordering = ["seq"]


class Funding(models.Model):
    """
    Fon bilgisi — Crossref/OpenAIRE uyumlu. OJS'te eklenti gerektirir; biz çekirdekte.
    """

    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="funders"
    )
    funder_name = models.CharField(max_length=255)
    funder_id = models.CharField(
        max_length=128, blank=True, help_text="Funder DOI or ROR (e.g. 10.13039/...)"
    )
    award_numbers = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.funder_name


class Galley(TimeStampedModel):
    """Yayının dağıtılabilir biçimi (PDF/HTML/XML). Yerel dosya veya uzak URL."""

    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="galleys"
    )
    locale = models.CharField(max_length=14, blank=True)
    label = models.CharField(max_length=64, help_text="e.g. PDF, HTML, XML")
    file = models.ForeignKey(
        "submissions.SubmissionFile", null=True, blank=True, on_delete=models.SET_NULL
    )
    remote_url = models.URLField(blank=True, max_length=2047)
    is_approved = models.BooleanField(default=False)
    url_path = models.SlugField(max_length=64, blank=True)
    seq = models.FloatField(default=0.0)
    doi = models.OneToOneField(
        "core.Doi", null=True, blank=True, on_delete=models.SET_NULL, related_name="galley"
    )

    class Meta:
        ordering = ["seq"]
        verbose_name = "Galley"
        verbose_name_plural = "Galleys"

    def __str__(self) -> str:
        return self.label


DEFAULT_PDF_BODY = """\
<article>
  <header class="cc-head">
    {% if logo_url %}<img class="cc-logo" src="{{ logo_url }}" alt="">{% endif %}
    <div class="cc-brand">{{ journal_title }}{% if issue_line %} · {{ issue_line }}{% endif %}</div>
  </header>

  <h1 class="cc-title">{{ title }}</h1>
  {% if subtitle %}<p class="cc-subtitle">{{ subtitle }}</p>{% endif %}

  <p class="cc-authors">{{ authors }}</p>
  {% if affiliations %}<p class="cc-affil">{{ affiliations|safe }}</p>{% endif %}

  <div class="cc-meta">
    {% if doi %}DOI: <a href="https://doi.org/{{ doi }}">{{ doi }}</a>{% endif %}
    {% if date_published %} &middot; {{ date_published }}{% endif %}
    {% if license_url %} &middot; <a href="{{ license_url }}">License</a>{% endif %}
  </div>

  {% if abstract %}<h2 class="cc-h2">Abstract</h2><div class="cc-abstract">{{ abstract }}</div>{% endif %}
  {% if keywords %}<p class="cc-kw"><strong>Keywords:</strong> {{ keywords }}</p>{% endif %}
  {% if body %}<hr class="cc-sep"><div class="cc-body">{{ body|safe }}</div>{% endif %}
</article>
"""

DEFAULT_PDF_CSS = """\
@page { size: A4; margin: 2.4cm 2cm;
  @bottom-center { content: "{{ journal_title }} · {{ doi }}"; font-size: 8pt; color: #888; } }
body { font-family: 'DejaVu Serif', Georgia, serif; color: #1a1a1a; font-size: 10.5pt; line-height: 1.5; }
.cc-head { display: flex; align-items: center; gap: 12px;
  border-bottom: 2px solid #1f3df2; padding-bottom: 8px; margin-bottom: 18px; }
.cc-logo { height: 40px; width: auto; }
.cc-brand { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 8.5pt;
  letter-spacing: .08em; text-transform: uppercase; color: #1f3df2; }
.cc-title { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 19pt; line-height: 1.2; margin: 0 0 6px; }
.cc-subtitle { font-size: 12pt; color: #555; margin: 0 0 10px; }
.cc-authors { font-size: 11pt; margin: 0 0 4px; }
.cc-affil { font-size: 9pt; color: #555; margin: 0 0 14px; }
.cc-meta { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 8.5pt; color: #555;
  background: #f5f5f3; padding: 8px 12px; border-radius: 6px; margin-bottom: 18px; }
.cc-meta a { color: #1f3df2; text-decoration: none; }
.cc-h2 { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10pt; text-transform: uppercase;
  letter-spacing: .06em; color: #444; margin: 18px 0 6px; }
.cc-abstract { text-align: justify; }
.cc-kw { font-size: 9pt; color: #555; margin-top: 12px; }
.cc-sep { border: none; border-top: 1px solid #ddd; margin: 22px 0; }
.cc-body { text-align: justify; }
.cc-body h2 { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 12pt; color: #1f3df2; margin: 18px 0 6px; }
.cc-body h3 { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; margin: 14px 0 5px; }
.cc-body p { margin: 0 0 9px; }
.cc-body ul, .cc-body ol { margin: 6px 0 12px 18px; }
.cc-body li { margin-bottom: 4px; }
.cc-body blockquote { border-left: 3px solid #ccc; margin: 10px 0; padding-left: 12px; color: #555; }
"""


DEFAULT_PDF_DESIGN = {
    "colors": {"accent": "#1f3df2", "accent2": "#3de8c0", "text": "#1a1a1a",
               "muted_text": "#555555", "bg": "#ffffff", "panel": "#f5f5f3",
               "rule": "#1f3df2"},
    "fonts": {"heading": "sans", "body": "serif"},
    "logo": {"show": True, "position": "left", "size": 44},
    "badge": {"show": False, "text": "RESEARCH ARTICLE", "color": "#1f3df2"},
    "rule": {"show": True, "width": 2},
    "page": {"size": "A4", "margin_top": 2.4, "margin_x": 2.0, "margin_bottom": 2.4,
             "footer": "{{ journal_title }} · {{ doi }}", "page_numbers": False},
    "sections": [
        {"id": "brand", "show": True},
        {"id": "badge", "show": False},
        {"id": "title", "show": True},
        {"id": "subtitle", "show": True},
        {"id": "authors", "show": True},
        {"id": "affiliations", "show": True},
        {"id": "meta", "show": True},
        {"id": "abstract", "show": True},
        {"id": "keywords", "show": True},
        {"id": "body", "show": True},
    ],
}


class PdfTemplate(TimeStampedModel):
    """Düzenlenebilir PDF galley şablonu (dergi başına).

    İki mod:
      * **visual** — `design` (JSON) görsel tasarımcıdan beslenir; HTML+CSS otomatik
        üretilir. Kod gerektirmez (renkler, fontlar, logo, bölüm sırası/görünürlüğü).
      * **html** — `body_html` + `css` ham düzenlenir (ileri kullanım).
    Her iki modda da render anında `{{ title }}`, `{{ authors }}` gibi değişkenler dolar.
    """

    class Mode(models.TextChoices):
        VISUAL = "visual", "Visual designer"
        HTML = "html", "Custom HTML/CSS"

    journal = models.ForeignKey("journals.Journal", on_delete=models.CASCADE,
                                related_name="pdf_templates")
    name = models.CharField(max_length=120, default="Default")
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.VISUAL)
    design = models.JSONField(default=dict, blank=True,
                              help_text="Visual designer settings (managed via the UI).")
    body_html = models.TextField(default=DEFAULT_PDF_BODY, blank=True,
                                 help_text="HTML + Django şablon değişkenleri "
                                 "({{ title }}, {{ authors }}, {{ abstract }}, "
                                 "{{ logo_url }}, {{ doi }}, {{ keywords }} …).")
    css = models.TextField(default=DEFAULT_PDF_CSS, blank=True,
                           help_text="Sayfa CSS'i (@page kuralları dahil). "
                           "Şablon değişkenleri burada da kullanılabilir.")
    page_size = models.CharField(max_length=16, default="A4",
                                 help_text="A4, Letter, A5 …")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "PDF template"
        verbose_name_plural = "PDF templates"


    def __str__(self) -> str:
        return f"{self.name} — {self.journal}"
