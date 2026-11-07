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
Düzenlenebilir navigasyon — OJS NavigationMenu/Item mantığı.

İki alan (area): primary (üst menü) ve user (kullanıcı menüsü). Öğeler statik sayfaya,
özel URL'ye veya bir sistem rotasına (home/archive/search/submit/login...) bağlanır.
Etiketler çok-dilli (MenuItemLabel); yoksa sayfa başlığına / sistem varsayılanına düşer.
"""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class MenuArea(models.TextChoices):
    PRIMARY = "primary", "Primary menu"
    USER = "user", "User menu"
    FOOTER = "footer", "Footer menu"


class MenuKind(models.TextChoices):
    SYSTEM = "system", "System route"
    PAGE = "page", "Static page"
    URL = "url", "Custom URL"


SYSTEM_TYPES = {
    "home":     (_("Home"),       ("web", "home"),     "all"),
    "archive":  (_("Archives"),   ("web", "archive"),  "all"),
    "search":   (_("Search"),     ("web", "search"),   "all"),
    "announcements": (_("Announcements"), ("web", "announcements"), "all"),
    "categories": (_("Categories"), ("web", "categories"), "all"),
    "submit":   (_("Submit"),     ("submit", "start"), "auth"),
    "login":    (_("Sign in"),    "/accounts/login/",  "anon"),
    "register": (_("Register"),   "/accounts/register/", "anon"),
    "logout":   (_("Sign out"),   "/accounts/logout/", "auth"),
    "dashboard": (_("My submissions"), "/dashboard/",  "auth"),
}


class MenuItem(models.Model):
    area = models.CharField(max_length=12, choices=MenuArea.choices, default=MenuArea.PRIMARY)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    kind = models.CharField(max_length=8, choices=MenuKind.choices, default=MenuKind.SYSTEM)
    system_key = models.CharField(max_length=24, blank=True,
                                  help_text="kind=system ise: home, archive, search, submit, "
                                            "login, register, logout, dashboard")
    page = models.ForeignKey("pages.StaticPage", null=True, blank=True, on_delete=models.CASCADE)
    url = models.CharField(max_length=255, blank=True, help_text="kind=url ise tam adres")
    seq = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["area", "seq"]
        verbose_name = "Menu Item"

    def __str__(self) -> str:
        return f"[{self.area}] {self.default_label()}"

    def default_label(self) -> str:
        if self.kind == MenuKind.SYSTEM and self.system_key in SYSTEM_TYPES:
            return str(SYSTEM_TYPES[self.system_key][0])
        if self.kind == MenuKind.PAGE and self.page_id:
            t = self.page.tr()
            return t.title if t else self.page.slug
        return self.url or "—"

    def visibility(self) -> str:
        if self.kind == MenuKind.SYSTEM and self.system_key in SYSTEM_TYPES:
            return SYSTEM_TYPES[self.system_key][2]
        return "all"


class MenuItemLabel(models.Model):
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="labels")
    locale = models.CharField(max_length=12)
    label = models.CharField(max_length=120)

    class Meta:
        unique_together = ("item", "locale")

    def __str__(self) -> str:
        return f"{self.item_id} [{self.locale}]"
