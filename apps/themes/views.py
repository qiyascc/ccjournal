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

from django.http import HttpResponse

from .services import active_theme, read_css


def theme_css(request):
    t = active_theme()
    css = read_css(t.key) if t else ""
    try:
        from apps.journals.models import Journal
        from apps.web.theme_editor import theme_overrides_css
        css += theme_overrides_css(Journal.current())
    except Exception:
        pass
    return HttpResponse(css, content_type="text/css")
