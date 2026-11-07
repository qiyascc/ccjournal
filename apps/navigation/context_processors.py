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

"""primary_menu + user_menu'yu tüm şablonlara enjekte eder."""
from django.conf import settings

from apps.journals.models import Journal

from .services import build_menu


def menus(request):
    journal = Journal.current()
    locale = (request.GET.get("lang")
              or (journal.primary_locale if journal else None)
              or settings.LANGUAGE_CODE)
    return {
        "primary_menu": build_menu("primary", request, locale),
        "user_menu": build_menu("user", request, locale),
        "footer_menu": build_menu("footer", request, locale),
    }
