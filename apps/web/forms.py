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

"""İlk kurulum sihirbazı formu."""
from django import forms

from apps.core.locales import LOCALE_CHOICES


class SetupForm(forms.Form):
    title = forms.CharField(max_length=255, label="Journal title")
    primary_locale = forms.ChoiceField(choices=LOCALE_CHOICES, label="Primary language")
    supported_locales = forms.MultipleChoiceField(
        choices=LOCALE_CHOICES, widget=forms.CheckboxSelectMultiple,
        label="Published languages", initial=["en"],
    )
    publisher = forms.CharField(max_length=255, required=False)
    contact_email = forms.EmailField(required=False)
    issn_online = forms.CharField(max_length=9, required=False, label="Online ISSN")
    logo = forms.ImageField(required=False)

    def clean(self):
        cd = super().clean()
        primary = cd.get("primary_locale")
        supported = cd.get("supported_locales") or []
        if primary and primary not in supported:
            cd["supported_locales"] = [primary, *supported]
        return cd
