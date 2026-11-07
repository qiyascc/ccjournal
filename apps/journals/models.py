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
Dergi (context) katmanı — çok-dergili mimarinin çekirdeği.

OJS gibi: tek kurulum N dergi barındırır. Her dergi URL yolu (`path`) ile erişilir:
``/{journal_path}/...``. İçerik (sayı, bölüm, gönderi) dergiye özeldir;
kullanıcılar global'dir.
"""
from __future__ import annotations

from django.db import models
from versatileimagefield.fields import VersatileImageField

from apps.core.models import TimeStampedModel, TranslatableMixin, validate_issn


class Journal(TimeStampedModel, TranslatableMixin):
    path = models.SlugField(max_length=64, unique=True, help_text="URL path segment")
    primary_locale = models.CharField(max_length=14, default="az")
    supported_locales = models.JSONField(default=list, help_text='örn. ["az","tr","en"]')
    seq = models.FloatField(default=1.0, help_text="Display order")
    enabled = models.BooleanField(default=True)

    issn_print = models.CharField(max_length=9, blank=True, validators=[validate_issn])
    issn_online = models.CharField(max_length=9, blank=True, validators=[validate_issn])
    publisher = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    doi_prefix = models.CharField(max_length=32, blank=True, help_text="e.g. 10.12345")

    enable_doi = models.BooleanField(default=False)
    enable_oai = models.BooleanField(default=True)
    default_review_mode = models.CharField(
        max_length=20,
        default="double_anonymous",
        choices=[
            ("open", "Open"),
            ("single_anonymous", "Single-anonymous"),
            ("double_anonymous", "Double-anonymous"),
        ],
    )

    theme = models.CharField(max_length=64, default="cc-default")
    logo = VersatileImageField(upload_to="journal/", blank=True)
    settings = models.JSONField(default=dict, blank=True, help_text="Theme / plugin settings")

    class Meta:
        ordering = ["seq", "path"]
        verbose_name = "Journal"
        verbose_name_plural = "Journal"

    def __str__(self) -> str:
        t = self.tr()
        return t.title if t else self.path

    @classmethod
    def current(cls):
        """
        Tek-dergi (single-journal) kurulumu: aktif dergiyi döndürür.
        Bu kurulum tek bir dergiye hizmet eder; admin ilk girişte onu oluşturur.
        """
        return cls.objects.filter(enabled=True).order_by("seq", "id").first()


class JournalTranslation(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="translations")
    locale = models.CharField(max_length=14)
    title = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    about = models.TextField(blank=True)
    editorial_team = models.TextField(blank=True)
    privacy_statement = models.TextField(blank=True)
    author_guidelines = models.TextField(blank=True)
    footer_text = models.TextField(
        blank=True, help_text="Altbilgi metni (boşsa © yıl + dergi adı gösterilir)")

    class Meta:
        unique_together = ("journal", "locale")
        verbose_name = "Journal Translation"

    def __str__(self) -> str:
        return f"{self.title} [{self.locale}]"


class Section(TimeStampedModel, TranslatableMixin):
    """Dergi içi içerik kategorisi: 'Makaleler', 'Derlemeler', 'Editörden'..."""

    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="sections")
    primary_locale = models.CharField(max_length=14, default="az")
    seq = models.FloatField(default=1.0)
    abstracts_required = models.BooleanField(default=True)
    is_indexed = models.BooleanField(default=True, help_text="Included in OAI / search index")
    is_editor_restricted = models.BooleanField(
        default=False, help_text="Only editors can submit to this section"
    )
    review_mode = models.CharField(max_length=20, blank=True, help_text="Empty = journal default")
    word_count_limit = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["seq"]
        verbose_name = "Section"
        verbose_name_plural = "Sections"

    def __str__(self) -> str:
        return self.tr_value("title") or f"Section #{self.pk}"


class SectionTranslation(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="translations")
    locale = models.CharField(max_length=14)
    title = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=32, blank=True)
    policy = models.TextField(blank=True)

    class Meta:
        unique_together = ("section", "locale")


class Issue(TimeStampedModel, TranslatableMixin):
    """Yayınlanmış makale koleksiyonu (cilt/sayı/yıl)."""

    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="issues")
    primary_locale = models.CharField(max_length=14, default="az")
    volume = models.PositiveIntegerField(null=True, blank=True)
    number = models.CharField(max_length=40, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)

    is_published = models.BooleanField(default=False, db_index=True)
    is_current = models.BooleanField(default=False, db_index=True)
    date_published = models.DateTimeField(null=True, blank=True)

    class Access(models.IntegerChoices):
        OPEN = 1, "Open access"
        SUBSCRIPTION = 2, "Subscription"

    access = models.IntegerField(choices=Access.choices, default=Access.OPEN, db_index=True)
    open_access_date = models.DateField(null=True, blank=True,
                                        help_text="Embargo lift date (open after this)")

    cover_image = VersatileImageField(upload_to="issues/covers/", blank=True)
    galley_file = models.FileField(
        upload_to="issues/galleys/", blank=True,
        help_text="Full-issue PDF (OJS issue galley); shown on the issue page "
                  "and gated by the access/paywall setting")
    doi = models.OneToOneField(
        "core.Doi", null=True, blank=True, on_delete=models.SET_NULL, related_name="issue"
    )

    class Meta:
        ordering = ["-year", "-volume", "-number"]
        verbose_name = "Issue"
        verbose_name_plural = "Issues"
        constraints = [
            models.UniqueConstraint(
                fields=["journal"],
                condition=models.Q(is_current=True),
                name="one_current_issue_per_journal",
            )
        ]

    def __str__(self) -> str:
        parts = []
        if self.volume:
            parts.append(f"C.{self.volume}")
        if self.number:
            parts.append(f"S.{self.number}")
        if self.year:
            parts.append(f"({self.year})")
        label = " ".join(parts) or self.tr_value("title") or f"Issue #{self.pk}"
        return f"{self.journal.path}: {label}"


class IssueTranslation(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="translations")
    locale = models.CharField(max_length=14)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ("issue", "locale")


class Category(TimeStampedModel, TranslatableMixin):
    """Hiyerarşik kategori (OJS Categories) — kategoriye göre gözat."""
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="categories")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True,
                               related_name="children")
    primary_locale = models.CharField(max_length=14, default="az")
    slug = models.SlugField(max_length=120)
    seq = models.FloatField(default=1.0)

    class Meta:
        ordering = ["seq"]
        unique_together = (("journal", "slug"),)
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        t = self.tr()
        return t.title if t else self.slug

    def descendant_ids(self):
        """Bu kategori + tüm alt kategorilerin id'leri."""
        ids, frontier = [self.pk], [self.pk]
        while frontier:
            kids = list(Category.objects.filter(parent_id__in=frontier)
                        .values_list("pk", flat=True))
            kids = [k for k in kids if k not in ids]
            ids.extend(kids)
            frontier = kids
        return ids


class CategoryTranslation(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="translations")
    locale = models.CharField(max_length=14)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ("category", "locale")

    def __str__(self) -> str:
        return f"{self.title} [{self.locale}]"


class ChecklistItem(TimeStampedModel):
    """Gönderi hazırlık kontrol listesi maddesi (OJS submission checklist)."""
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="checklist_items")
    seq = models.FloatField(default=1.0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["seq"]
        verbose_name = "Checklist item"

    def __str__(self) -> str:
        t = self.content_for(self.journal.primary_locale if self.journal_id else "en")
        return (t[:60] if t else f"Checklist #{self.pk}")

    def content_for(self, locale: str | None = None) -> str:
        items = {t.locale: t.content for t in self.translations.all()}
        if locale and locale in items:
            return items[locale]
        prim = self.journal.primary_locale if self.journal_id else "en"
        return items.get(prim) or (next(iter(items.values()), ""))


class ChecklistItemTranslation(models.Model):
    item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE, related_name="translations")
    locale = models.CharField(max_length=14)
    content = models.TextField()

    class Meta:
        unique_together = ("item", "locale")


class CallForPapers(TimeStampedModel):
    """Çağrı (CFP) / özel sayı duyurusu — /calls/ sayfası + ana sayfa bandı."""
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="calls")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    url = models.CharField(max_length=512, blank=True,
                           help_text="Ayrıntı bağlantısı (boşsa /calls/ metni yeter)")
    seq = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["seq", "-created_at"]
        verbose_name = "Call for papers"
        verbose_name_plural = "Calls for papers"

    def __str__(self) -> str:
        return self.title


class Highlight(TimeStampedModel, TranslatableMixin):
    """Ana sayfa öne çıkanlar karuseli (OJS 3.5 Highlights).

    Duyuru/CFP/öne çıkan makale gibi içerikler; görsel + başlık + kısa metin +
    hedef URL. Yalnız aktif olanlar sırayla gösterilir.
    """
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="highlights")
    primary_locale = models.CharField(max_length=14, default="az")
    image = VersatileImageField(upload_to="highlights/", blank=True)
    url = models.CharField(max_length=512, blank=True,
                           help_text="Target link (e.g. /article/12/ or a full URL)")
    seq = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["seq", "id"]
        verbose_name = "Highlight"
        verbose_name_plural = "Highlights"

    def __str__(self) -> str:
        return self.tr_value("title") or f"Highlight #{self.pk}"


class HighlightTranslation(models.Model):
    highlight = models.ForeignKey(Highlight, on_delete=models.CASCADE,
                                  related_name="translations")
    locale = models.CharField(max_length=14)
    title = models.CharField(max_length=255)
    blurb = models.CharField(max_length=500, blank=True)
    cta = models.CharField(max_length=64, blank=True, help_text='Button label, e.g. "Read more"')

    class Meta:
        unique_together = ("highlight", "locale")
