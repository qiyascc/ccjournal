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

"""Tüm OJS dilleri için e-posta şablonu satırlarını oluşturur."""
from django.db import migrations


def seed_all(apps, schema_editor):
    from apps.comms.seeding import seed
    from apps.core.locales import CONTENT_LOCALES
    EmailTemplate = apps.get_model("comms", "EmailTemplate")
    seed(EmailTemplate, [code for code, _, _ in CONTENT_LOCALES])


def unseed(apps, schema_editor):
    pass  # 0002'nin geri-alımına dokunmuyoruz


class Migration(migrations.Migration):
    dependencies = [("comms", "0002_seed_templates")]
    operations = [migrations.RunPython(seed_all, unseed)]
