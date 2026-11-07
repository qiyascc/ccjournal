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

"""form.<domain> isteklerini form urlconf'una yönlendirir.

Subdomain config.ini'den okunur:  [forms] subdomain = form   (varsayılan: form)
Admin'deki Config ekranından da değiştirilebilir (çift-yazma).
"""


class FormSubdomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from apps.configuration.services import Config
            sub = (Config.get("forms", "subdomain", "form") or "form").strip().lower()
            host = request.get_host().split(":")[0].lower()
            if sub and host.split(".")[0] == sub and host.count(".") >= 1:
                request.urlconf = "apps.formbuilder.urls_subdomain"
        except Exception:
            pass
        return self.get_response(request)
