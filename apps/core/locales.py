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
İçerik dilleri (content locales).

Admin arayüzü İngilizce'dir (settings.LANGUAGE_CODE = "en"); ancak derginin
YAYIN içeriği OJS'teki gibi çok dillidir. Dergi kurulurken bu listeden desteklenen
diller seçilir. (code, English name, native name) — OJS/Weblate dil setine yakın.
"""
from __future__ import annotations

CONTENT_LOCALES: list[tuple[str, str, str]] = [
    ("az", "Azerbaijani", "Azərbaycan"),
    ("tr", "Turkish", "Türkçe"),
    ("en", "English", "English"),
    ("ru", "Russian", "Русский"),
    ("ar", "Arabic", "العربية"),
    ("fa", "Persian", "فارسی"),
    ("de", "German", "Deutsch"),
    ("fr", "French", "Français"),
    ("es", "Spanish", "Español"),
    ("pt-BR", "Portuguese (Brazil)", "Português (Brasil)"),
    ("pt-PT", "Portuguese (Portugal)", "Português (Portugal)"),
    ("it", "Italian", "Italiano"),
    ("nl", "Dutch", "Nederlands"),
    ("pl", "Polish", "Polski"),
    ("uk", "Ukrainian", "Українська"),
    ("kk", "Kazakh", "Қазақ"),
    ("ky", "Kyrgyz", "Кыргызча"),
    ("uz", "Uzbek", "Oʻzbek"),
    ("tk", "Turkmen", "Türkmen"),
    ("ka", "Georgian", "ქართული"),
    ("hy", "Armenian", "Հայերեն"),
    ("el", "Greek", "Ελληνικά"),
    ("he", "Hebrew", "עברית"),
    ("hi", "Hindi", "हिन्दी"),
    ("bn", "Bengali", "বাংলা"),
    ("ur", "Urdu", "اردو"),
    ("id", "Indonesian", "Bahasa Indonesia"),
    ("ms", "Malay", "Bahasa Melayu"),
    ("vi", "Vietnamese", "Tiếng Việt"),
    ("th", "Thai", "ไทย"),
    ("zh-Hans", "Chinese (Simplified)", "简体中文"),
    ("zh-Hant", "Chinese (Traditional)", "繁體中文"),
    ("ja", "Japanese", "日本語"),
    ("ko", "Korean", "한국어"),
    ("cs", "Czech", "Čeština"),
    ("sk", "Slovak", "Slovenčina"),
    ("sl", "Slovenian", "Slovenščina"),
    ("hr", "Croatian", "Hrvatski"),
    ("sr", "Serbian", "Српски"),
    ("ro", "Romanian", "Română"),
    ("bg", "Bulgarian", "Български"),
    ("hu", "Hungarian", "Magyar"),
    ("fi", "Finnish", "Suomi"),
    ("sv", "Swedish", "Svenska"),
    ("nb", "Norwegian Bokmål", "Norsk bokmål"),
    ("da", "Danish", "Dansk"),
    ("ca", "Catalan", "Català"),
    ("eu", "Basque", "Euskara"),
    ("gl", "Galician", "Galego"),
    ("af", "Afrikaans", "Afrikaans"),
    ("sw", "Swahili", "Kiswahili"),
]

LOCALE_CHOICES = [
    (code, f"{en}" if en == native else f"{en} ({native})")
    for code, en, native in CONTENT_LOCALES
]

VALID_LOCALE_CODES = {code for code, _, _ in CONTENT_LOCALES}


def locale_label(code: str) -> str:
    for c, en, native in CONTENT_LOCALES:
        if c == code:
            return f"{en} ({native})" if en != native else en
    return code
