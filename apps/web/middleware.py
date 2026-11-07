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
İlk kurulum yönlendirmesi: dergi yapılandırılmamışsa superuser'ı /setup/'a yönlendirir,
diğer ziyaretçilere "kuruluyor" sayfası gösterir.
"""
from django.shortcuts import redirect, render

from apps.journals.models import Journal

_EXEMPT = ("/setup", "/admin", "/accounts", "/static", "/media", "/oai", "/export",
           "/theme.css", "/ckeditor5", "/rosetta", "/health", "/reports", "/api", "/manage", "/hijack", "/forms")


class SetupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith(_EXEMPT):
            if Journal.current() is None:
                user = getattr(request, "user", None)
                if user and user.is_authenticated and user.is_superuser:
                    return redirect("web:setup")
                return render(request, "web/needs_setup.html", status=503)
            try:
                from constance import config
                user = getattr(request, "user", None)
                if config.MAINTENANCE_MODE and not (user and user.is_staff):
                    return render(request, "web/maintenance.html",
                                  {"message": config.MAINTENANCE_MESSAGE}, status=503)
            except Exception:
                pass
        return self.get_response(request)
