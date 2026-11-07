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

"""Tema keşfi, aktif tema ve CSS okuma."""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

from .models import InstalledTheme


def themes_dir() -> Path:
    d = Path(settings.BASE_DIR) / "themes"
    d.mkdir(exist_ok=True)
    return d


def read_manifest(key: str) -> dict:
    p = themes_dir() / key / "theme.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def discover() -> int:
    """themes/ klasörünü tarayıp DB ile senkronlar; en az bir aktif tema garantiler."""
    n = 0
    for d in sorted(themes_dir().iterdir()):
        if not d.is_dir() or not (d / "theme.json").exists():
            continue
        m = read_manifest(d.name)
        InstalledTheme.objects.update_or_create(
            key=m.get("key", d.name),
            defaults={"name": m.get("name", d.name), "version": m.get("version", "1.0.0"),
                      "author": m.get("author", ""), "description": m.get("description", "")},
        )
        n += 1
    if not InstalledTheme.objects.filter(is_active=True).exists():
        default = (InstalledTheme.objects.filter(key="broadsheet").first()
                   or InstalledTheme.objects.filter(key="default").first()
                   or InstalledTheme.objects.first())
        if default:
            default.is_active = True
            default.save()
    return n


def active_theme() -> InstalledTheme | None:
    return (InstalledTheme.objects.filter(is_active=True).first()
            or InstalledTheme.objects.filter(key="broadsheet").first()
            or InstalledTheme.objects.filter(key="default").first()
            or InstalledTheme.objects.first())


def read_css(key: str) -> str:
    p = themes_dir() / key / "theme.css"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def set_active(key: str) -> bool:
    t = InstalledTheme.objects.filter(key=key).first()
    if not t:
        return False
    t.is_active = True
    t.save()
    return True


def validate_theme(key: str) -> tuple[bool, str]:
    """Temayı aktif etmeden önce sağlık kontrolü:
    1) theme.json geçerli mi, 2) tüm şablonlar derleniyor mu (sözdizimi),
    3) ana sayfa gerçekten render oluyor mu (çalışma-anı hatası)."""
    import json as _json
    import traceback

    d = themes_dir() / key
    try:
        _json.loads((d / "theme.json").read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return False, f"theme.json parse error: {e}"

    from django.template import Template, TemplateSyntaxError
    tdir = d / "templates"
    if tdir.exists():
        for p in sorted(tdir.rglob("*.html")):
            try:
                Template(p.read_text(encoding="utf-8"))
            except TemplateSyntaxError as e:
                rel = p.relative_to(d)
                return False, f"Template syntax error in {rel}:\n{e}"
            except Exception as e:  # noqa: BLE001
                rel = p.relative_to(d)
                return False, f"Template error in {rel}:\n{e}"

    try:
        from django.test import Client
        resp = Client(raise_request_exception=True).get("/", follow=True)
        if resp.status_code >= 500:
            return False, f"Homepage returned HTTP {resp.status_code} with this theme."
    except Exception:
        return False, "Homepage failed to render with this theme:\n" + traceback.format_exc(limit=6)
    return True, ""


def safe_activate(key: str, user=None) -> dict:
    """Temayı doğrulayarak aktive eder; sorun çıkarsa öncekini geri yükler.

    Dönen sözlük: {ok, error, rolled_back_to} — admin mesajı/bildirimi için.
    """
    from . import loaders
    prev = active_theme()
    prev_key = prev.key if prev else None

    if not set_active(key):
        return {"ok": False, "error": f"Theme '{key}' not found.", "rolled_back_to": prev_key}
    loaders.invalidate()

    ok, error = validate_theme(key)
    if ok:
        return {"ok": True, "error": "", "rolled_back_to": None}

    if prev_key and prev_key != key:
        set_active(prev_key)
        loaders.invalidate()
    _notify_theme_failure(key, prev_key, error, user)
    return {"ok": False, "error": error, "rolled_back_to": prev_key}


def _notify_theme_failure(key, prev_key, error, user):
    """In-app bildirim + (yapılandırılmışsa) tarayıcı push'u — İngilizce."""
    title = "Theme rollback"
    body = (f"The theme you just uploaded ('{key}') caused an error, so I re-activated "
            f"the previous theme ('{prev_key}'). Fix the error and try again.")
    try:
        from apps.comms.services import NotifyService
        from apps.journals.models import Journal
        j = Journal.current()
        targets = {user.pk: user} if user else {}
        from apps.accounts.models import User
        for u in User.objects.filter(is_superuser=True, is_active=True):
            targets.setdefault(u.pk, u)
        for u in targets.values():
            NotifyService.create(u, "theme_rollback", title, body=body, journal=j,
                                 url="/admin/themes/installedtheme/")
    except Exception:
        pass
    try:
        from apps.comms.push import push_to_superusers, push_to_user
        if user:
            push_to_user(user, title, body, url="/admin/themes/installedtheme/")
        push_to_superusers(title, body, url="/admin/themes/installedtheme/")
    except Exception:
        pass
