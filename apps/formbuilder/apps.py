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

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FormbuilderConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.formbuilder"
    label = "formbuilder"
    verbose_name = "Form builder"

    def ready(self):
        post_migrate.connect(_seed, sender=self)


def _seed(sender, **kwargs):
    """Varsayılan submission formu + config anahtarları (yoksa)."""
    from apps.configuration.services import Config
    from .models import FieldType, Form, FormField
    if Config.get("forms", "subdomain", None) is None:
        try:
            Config.set("forms", "subdomain", "form")
        except Exception:
            pass
    if Form.objects.filter(slug="submission").exists():
        return
    f = Form.objects.create(
        slug="submission", title="Article Submission",
        description="Submit your manuscript to the journal. Fill in the author and "
                    "article details below; our editorial team will review it.",
        is_protected=True, seq=0)
    rows = [
        ("First name", "first_name", FieldType.TEXT, True, "", "", []),
        ("Last name", "last_name", FieldType.TEXT, True, "", "", []),
        ("Email", "email", FieldType.EMAIL, True, "", "", []),
        ("Phone number", "phone", FieldType.PHONE, True, "", "+994 …", []),
        ("Article language", "language", FieldType.LOCALE, True,
         "Languages supported by the journal", "", []),
        ("ORCID iD", "orcid", FieldType.ORCID, False,
         "Accepted as 0000-0000-0000-0000 or 16 digits", "", []),
        ("Article title", "title", FieldType.TEXT, True, "", "", []),
        ("Abstract", "abstract", FieldType.TEXTAREA, True, "", "", []),
        ("Keywords", "keywords", FieldType.KEYWORDS, True,
         "Separate with commas", "", []),
        ("Affiliation", "affiliation", FieldType.TEXT, True,
         "Institution / university", "", []),
        ("Article file", "file", FieldType.FILE, True,
         "DOC, DOCX or PDF", "", []),
    ]
    for i, (label, slug, ftype, req, help_text, ph, choices) in enumerate(rows):
        FormField.objects.create(form=f, label=label, slug=slug, field_type=ftype,
                                 required=req, help_text=help_text, placeholder=ph,
                                 choices=choices, seq=i)
