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
Arayüz dili yönetimi — iki mod (config.ini → [language] url_type):

* query (varsayılan): ?lang=xx tek switcher'dır; bu middleware dilin tek yetkilisidir.
* slug: /xx/... öneki Django LocaleMiddleware tarafından çözülür ve reverse()
  tüm linkleri otomatik önekler; bu middleware yalnızca admin/rosetta'yı İngilizce'ye
  sabitler ve ?lang'ı (geri-uyum) öneğe yönlendirir.
"""
from django.conf import settings
from django.shortcuts import redirect
from django.utils import translation

_ADMIN_PREFIXES = ("/admin", "/rosetta")


class InterfaceLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.slug_mode = getattr(settings, "LANGUAGE_URL_TYPE", "query") == "slug"

    def __call__(self, request):
        if request.path.startswith(_ADMIN_PREFIXES):
            translation.activate(settings.LANGUAGE_CODE)
            request.LANGUAGE_CODE = settings.LANGUAGE_CODE
            try:
                return self.get_response(request)
            finally:
                translation.deactivate()

        if self.slug_mode:
            lang = request.GET.get("lang")
            if lang and lang.lower() in dict(settings.LANGUAGES):
                return redirect(switch_lang_path(request.path, lang.lower()))
            return self.get_response(request)

        lang = request.GET.get("lang")
        if lang:
            request.session["lang"] = lang
        else:
            lang = request.session.get("lang")
        if not lang:
            try:
                from apps.journals.models import Journal
                j = Journal.current()
                lang = j.primary_locale if j else settings.LANGUAGE_CODE
            except Exception:
                lang = settings.LANGUAGE_CODE
        translation.activate(lang)
        request.LANGUAGE_CODE = translation.get_language()
        try:
            return self.get_response(request)
        finally:
            translation.deactivate()


def strip_lang_prefix(path: str) -> str:
    """/az/issues/ -> /issues/ (önek LANGUAGES'tan biriyse)."""
    parts = path.split("/", 2)
    if len(parts) >= 2 and parts[1].lower() in dict(settings.LANGUAGES):
        rest = parts[2] if len(parts) > 2 else ""
        return "/" + rest
    return path


def switch_lang_path(path: str, code: str) -> str:
    """Geçerli yolu hedef dile çevirir (slug modu). Varsayılan dil öneksizdir."""
    bare = strip_lang_prefix(path)
    if code == settings.LANGUAGE_CODE:
        return bare
    return f"/{code}{bare}"
