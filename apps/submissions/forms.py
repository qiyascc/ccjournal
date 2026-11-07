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

"""Gönderi sihirbazı formları."""
from __future__ import annotations

from django import forms

from apps.core.locales import locale_label
from apps.journals.models import Journal, Section


class StartForm(forms.Form):
    section = forms.ModelChoiceField(queryset=Section.objects.none(), label="Section")
    locale = forms.ChoiceField(label="Submission language")

    def __init__(self, *args, journal: Journal | None = None, locale: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        journal = journal or Journal.current()
        self._checklist_names = []
        if journal:
            qs = journal.sections.all()
            self.fields["section"].queryset = qs.filter(is_editor_restricted=False)
            self.fields["locale"].choices = [
                (code, locale_label(code)) for code in (journal.supported_locales or [journal.primary_locale])
            ]
            loc = locale or journal.primary_locale
            items = list(journal.checklist_items.all().prefetch_related("translations"))
            for it in items:
                name = f"chk_{it.pk}"
                self.fields[name] = forms.BooleanField(
                    required=it.is_required, label=it.content_for(loc))
                self._checklist_names.append(name)
            if not items:
                self.fields["agree"] = forms.BooleanField(
                    label="I confirm the submission meets the journal's requirements.")
                self._checklist_names.append("agree")

    @property
    def checklist_fields(self):
        return [self[n] for n in self._checklist_names]


class MetadataForm(forms.Form):
    title = forms.CharField(max_length=512, label="Title")
    subtitle = forms.CharField(max_length=512, required=False, label="Subtitle")
    abstract = forms.CharField(widget=forms.Textarea, required=False, label="Abstract")
    keywords = forms.CharField(
        required=False, label="Keywords",
        help_text="Comma-separated", widget=forms.TextInput,
    )
