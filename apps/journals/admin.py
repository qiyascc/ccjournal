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

from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.core.locales import LOCALE_CHOICES, locale_label
from .models import (
    CallForPapers, Category, CategoryTranslation, ChecklistItem,
    ChecklistItemTranslation, Highlight, HighlightTranslation, Issue,
    IssueTranslation, Journal, JournalTranslation, Section, SectionTranslation,
)


@admin.register(CallForPapers)
class CallForPapersAdmin(ModelAdmin):
    list_display = ("title", "journal", "deadline", "seq", "is_active")
    list_filter = ("journal", "is_active")
    list_editable = ("seq", "is_active")


class HighlightTranslationInline(TabularInline):
    model = HighlightTranslation
    extra = 1
    tab = True


@admin.register(Highlight)
class HighlightAdmin(ModelAdmin):
    inlines = [HighlightTranslationInline]
    list_display = ("__str__", "journal", "url", "seq", "is_active")
    list_filter = ("journal", "is_active")
    list_editable = ("seq", "is_active")


class JournalForm(forms.ModelForm):
    """supported_locales (JSONField list) -> kullanıcı dostu çoklu seçim (OJS gibi)."""

    supported_locales = forms.MultipleChoiceField(
        choices=LOCALE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text="Select the languages this journal will publish in.",
    )
    primary_locale = forms.ChoiceField(choices=LOCALE_CHOICES)

    class Meta:
        model = Journal
        fields = "__all__"


class JournalTranslationInline(TabularInline):
    model = JournalTranslation
    extra = 1
    tab = True


@admin.register(Journal)
class JournalAdmin(ModelAdmin):
    form = JournalForm
    inlines = [JournalTranslationInline]
    list_display = ("path", "publisher", "primary_locale", "enabled")
    search_fields = ("path", "publisher")
    fieldsets = (
        ("Identity", {"fields": ("path", "primary_locale", "supported_locales", "enabled", "seq")}),
        ("Bibliographic", {"fields": ("publisher", "issn_print", "issn_online", "contact_email")}),
        ("DOI & Indexing", {"fields": ("enable_doi", "doi_prefix", "enable_oai")}),
        ("Workflow", {"fields": ("default_review_mode",)}),
        ("Appearance", {"fields": ("theme", "settings")}),
    )

    def has_add_permission(self, request):
        if Journal.objects.exists():
            return False
        return super().has_add_permission(request)


class SectionTranslationInline(TabularInline):
    model = SectionTranslation
    extra = 1
    tab = True


@admin.register(Section)
class SectionAdmin(ModelAdmin):
    inlines = [SectionTranslationInline]
    list_display = ("__str__", "journal", "seq", "abstracts_required", "is_indexed")
    list_filter = ("journal", "is_indexed", "is_editor_restricted")
    search_fields = ("translations__title",)


class IssueTranslationInline(TabularInline):
    model = IssueTranslation
    extra = 1
    tab = True


@admin.register(Issue)
class IssueAdmin(ModelAdmin):
    inlines = [IssueTranslationInline]
    list_display = ("__str__", "year", "access", "is_published", "is_current", "date_published")
    list_filter = ("journal", "access", "is_published", "is_current", "year")
    search_fields = ("translations__title", "number")
    actions = ["action_issue_checklist", "action_publish_issue",
               "action_unpublish_issue"]

    @admin.action(description="Pre-publish checklist…")
    def action_issue_checklist(self, request, queryset):
        """Sayı kapanış asistanı: yayınlamadan önce eksikleri tek ekranda göster."""
        from django.contrib import messages
        from django.core.exceptions import ValidationError
        from django.shortcuts import render
        from apps.publications.services import PublicationService
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one issue.",
                              level=messages.ERROR)
            return None
        issue = queryset.first()
        rows = []
        for pub in (issue.publications.select_related("section")
                    .prefetch_related("translations", "galleys")):
            try:
                PublicationService.validate_publish(pub)
                problems = []
            except ValidationError as exc:
                problems = list(exc.messages)
            t = (pub.translations.filter(locale=pub.primary_locale).first()
                 or pub.translations.first())
            rows.append({"pub": pub,
                         "title": (t.title if t else f"Publication #{pub.pk}"),
                         "problems": problems})
        issue_problems = []
        if not rows:
            issue_problems.append("No articles are assigned to this issue.")
        if not issue.cover_image:
            issue_problems.append("No cover image uploaded (optional but recommended).")
        if not issue.galley_file:
            issue_problems.append("No full-issue PDF uploaded (optional).")
        return render(request, "admin/issue_check.html", {
            "issue": issue, "rows": rows, "issue_problems": issue_problems,
            "ready": all(not r["problems"] for r in rows) and bool(rows),
        })

    @admin.action(description="Publish issue (and its scheduled articles)")
    def action_publish_issue(self, request, queryset):
        from apps.publications.services import IssueService
        for issue in queryset:
            IssueService.publish_issue(issue)
        self.message_user(request, "Issue(s) published; scheduled articles released.")

    @admin.action(description="Unpublish issue")
    def action_unpublish_issue(self, request, queryset):
        from apps.publications.services import IssueService
        for issue in queryset:
            IssueService.unpublish_issue(issue)
        self.message_user(request, "Issue(s) unpublished; articles reverted to scheduled.")


def _cat_supported():
    j = Journal.current()
    return (list(j.supported_locales) if j else ["en"], j.primary_locale if j else "en")


class BaseCategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("parent", "slug", "seq")


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("indented_title", "slug", "seq")
    search_fields = ("slug", "translations__title")
    autocomplete_fields = ("parent",)
    ordering = ("parent__id", "seq")

    def get_form(self, request, obj=None, **kwargs):
        locales, primary = _cat_supported()
        existing = {t.locale: t for t in obj.translations.all()} if obj and obj.pk else {}
        attrs = {"_locales": locales}
        for loc in locales:
            label = locale_label(loc)
            t = existing.get(loc)
            attrs[f"title_{loc}"] = forms.CharField(
                label=f"Title · {label}", required=(loc == primary),
                initial=(t.title if t else ""))
            attrs[f"desc_{loc}"] = forms.CharField(
                label=f"Description · {label}", required=False,
                widget=forms.Textarea(attrs={"rows": 3}),
                initial=(t.description if t else ""))
        kwargs["form"] = type("CategoryForm", (BaseCategoryForm,), attrs)
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        locales, _ = _cat_supported()
        base = [(None, {"fields": ("parent", "slug", "seq")})]
        return base + [(locale_label(loc), {"fields": (f"title_{loc}", f"desc_{loc}")})
                       for loc in locales]

    @admin.display(description="Title")
    def indented_title(self, obj):
        depth = 0
        p = obj.parent
        while p and depth < 6:
            depth += 1
            p = p.parent
        return ("— " * depth) + str(obj)

    def save_model(self, request, obj, form, change):
        if obj.journal_id is None:
            obj.journal = Journal.current()
        super().save_model(request, obj, form, change)
        supported = set(getattr(form, "_locales", []))
        for loc in supported:
            title = (form.cleaned_data.get(f"title_{loc}") or "").strip()
            desc = form.cleaned_data.get(f"desc_{loc}") or ""
            if title or desc:
                CategoryTranslation.objects.update_or_create(
                    category=obj, locale=loc,
                    defaults={"title": title or obj.slug, "description": desc})
            else:
                CategoryTranslation.objects.filter(category=obj, locale=loc).delete()
        CategoryTranslation.objects.filter(category=obj).exclude(locale__in=supported).delete()


class BaseChecklistForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ("seq", "is_required")


@admin.register(ChecklistItem)
class ChecklistItemAdmin(ModelAdmin):
    list_display = ("__str__", "languages", "is_required", "seq")
    list_editable = ("is_required", "seq")

    def get_form(self, request, obj=None, **kwargs):
        locales, primary = _cat_supported()
        existing = {t.locale: t for t in obj.translations.all()} if obj and obj.pk else {}
        attrs = {"_locales": locales}
        for loc in locales:
            t = existing.get(loc)
            attrs[f"content_{loc}"] = forms.CharField(
                label=f"Content · {locale_label(loc)}", required=(loc == primary),
                widget=forms.Textarea(attrs={"rows": 2}),
                initial=(t.content if t else ""))
        kwargs["form"] = type("ChecklistItemForm", (BaseChecklistForm,), attrs)
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        locales, _ = _cat_supported()
        return [(None, {"fields": ("seq", "is_required")})] + \
               [(locale_label(loc), {"fields": (f"content_{loc}",)}) for loc in locales]

    @admin.display(description="Languages")
    def languages(self, obj):
        return ", ".join(t.locale for t in obj.translations.all()) or "—"

    def save_model(self, request, obj, form, change):
        if obj.journal_id is None:
            obj.journal = Journal.current()
        super().save_model(request, obj, form, change)
        supported = set(getattr(form, "_locales", []))
        for loc in supported:
            content = (form.cleaned_data.get(f"content_{loc}") or "").strip()
            if content:
                ChecklistItemTranslation.objects.update_or_create(
                    item=obj, locale=loc, defaults={"content": content})
            else:
                ChecklistItemTranslation.objects.filter(item=obj, locale=loc).delete()
        ChecklistItemTranslation.objects.filter(item=obj).exclude(locale__in=supported).delete()
