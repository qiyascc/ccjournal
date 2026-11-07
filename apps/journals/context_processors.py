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

"""Tüm şablonlara dergi markasını (ad + logo) sağlar — whitelabel."""
from .models import Journal


def branding(request):
    journal = Journal.current()
    title = ""
    logo_url = ""
    if journal:
        t = journal.tr()
        title = t.title if t else journal.path
        if journal.logo:
            try:
                logo_url = journal.logo.url
            except Exception:
                logo_url = ""
    return {"site_journal": journal, "site_title": title, "site_logo": logo_url}
