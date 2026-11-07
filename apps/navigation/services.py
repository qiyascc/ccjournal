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

"""Menü kurucu + varsayılan tohumlama."""
from __future__ import annotations

from django.urls import NoReverseMatch, reverse

from .models import MenuArea, MenuItem, MenuKind, SYSTEM_TYPES


def _resolve_url(item) -> str:
    if item.kind == MenuKind.PAGE and item.page_id:
        try:
            return reverse("web:page", kwargs={"slug": item.page.slug})
        except NoReverseMatch:
            return "#"
    if item.kind == MenuKind.URL:
        return item.url or "#"
    if item.kind == MenuKind.SYSTEM and item.system_key in SYSTEM_TYPES:
        target = SYSTEM_TYPES[item.system_key][1]
        if isinstance(target, tuple):
            try:
                return reverse(f"{target[0]}:{target[1]}")
            except NoReverseMatch:
                return "#"
        return target
    return "#"


def _visible_v(vis: str, request) -> bool:
    u = getattr(request, "user", None)
    auth = bool(u and u.is_authenticated)
    if vis == "anon":
        return not auth
    if vis == "auth":
        return auth
    if vis == "staff":
        return bool(u and u.is_staff)
    return True


def _label(item, locale: str) -> str:
    for lab in item.labels.all():
        if lab.locale == locale:
            return lab.label
    if item.kind == MenuKind.PAGE and item.page_id:
        t = item.page.tr(locale)
        return t.title if t else item.page.slug
    return item.default_label()


def _build_menu_data(area: str, locale: str) -> list[dict]:
    """DB-ağır menü verisi (görünürlükten/istekten bağımsız) — cache'lenir."""
    roots = (MenuItem.objects.filter(area=area, parent=None, is_enabled=True)
             .order_by("seq")
             .prefetch_related("labels", "children", "children__labels", "page__translations"))
    data = []
    for item in roots:
        children = [{"label": _label(ch, locale), "url": _resolve_url(ch),
                     "visibility": ch.visibility()}
                    for ch in item.children.all() if ch.is_enabled]
        data.append({"label": _label(item, locale), "url": _resolve_url(item),
                     "visibility": item.visibility(), "children": children})
    return data


def build_menu(area: str, request, locale: str) -> list[dict]:
    """İstek başına: sürüm-cache'li veriye görünürlük + 'active' uygular (DB'ye vurmaz)."""
    from apps.core.cache import cached_by_version
    data = cached_by_version(f"nav:{area}:{locale}",
                             lambda: _build_menu_data(area, locale))
    out = []
    for item in data:
        if not _visible_v(item["visibility"], request):
            continue
        children = [{"label": c["label"], "url": c["url"]} for c in item["children"]
                    if _visible_v(c["visibility"], request)]
        url = item["url"]
        out.append({"label": item["label"], "url": url, "children": children,
                    "active": request.path == url and url != "#"})
    return out


DEFAULTS = {
    "footer": ["archive", "search", "announcements", "categories"],
    MenuArea.PRIMARY: ["home", "archive", "search", "submit"],
    MenuArea.USER: ["login", "register", "dashboard", "logout"],
}


def seed_menus_if_empty() -> int:
    if MenuItem.objects.exists():
        return 0
    n = 0
    for area, keys in DEFAULTS.items():
        for i, key in enumerate(keys):
            MenuItem.objects.create(area=area, kind=MenuKind.SYSTEM, system_key=key, seq=i)
            n += 1
    return n
