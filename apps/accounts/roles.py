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
Rol kataloğu — OJS rolleri Django Group olarak.

Yaklaşım: her rol bir Django Group'tur; kullanıcı oluştururken/düzenlerken gruba
atanır (Django'nun yerleşik groups M2M'i). İzinler model-seviyesinde gruba verilir;
nesne-seviyesi kapsam (ör. hakem yalnızca atandığı gönderiyi görür) servis/view
katmanında uygulanır — tıpkı OJS'in assignment tabanlı kapsamı gibi.

`perms` biçimi: "all"  veya  [(app_label, models("*" | [..]), actions("*" | [..]))]
"""
from __future__ import annotations

from django.db import models

_ALL_ACTIONS = ("add", "change", "delete", "view")
_EDIT = ("view", "change")
_VIEW = ("view",)
_CRUD = ("add", "change", "delete", "view")

_EDITORIAL_APPS = ["submissions", "publications", "review"]

ROLE_CATALOG = [
    dict(key="site_administrator", name="Site Administrator", category="admin",
         staff=True, perms="all"),
    dict(key="developer", name="Developer", category="admin",
         staff=True, perms="all"),

    dict(key="journal_manager", name="Journal Manager", category="admin", staff=True,
         perms=[("journals", "*", _CRUD), ("submissions", "*", _CRUD),
                ("publications", "*", _CRUD), ("review", "*", _CRUD),
                ("comms", "*", _CRUD), ("formbuilder", "*", "*"),
                ("metadata", "*", _CRUD), ("pages", "*", _CRUD),
                ("announcements", "*", _CRUD), ("navigation", "*", _CRUD),
                ("subscriptions", "*", _CRUD), ("stats", "*", _VIEW),
                ("accounts", ["journalmembership", "user", "apikey"], _EDIT)]),

    dict(key="editor", name="Editor", category="editorial", staff=True,
         perms=[("journals", ["section", "issue", "category", "checklistitem"], _EDIT),
                ("submissions", "*", _CRUD), ("publications", "*", _CRUD),
                ("review", "*", _CRUD), ("metadata", "*", _VIEW),
                ("comms", ["emailtemplate"], _VIEW),
                ("formbuilder", "*", "*")]),
    dict(key="section_editor", name="Section Editor", category="editorial", staff=True,
         perms=[("submissions", "*", _EDIT), ("publications", "*", _EDIT),
                ("review", "*", _CRUD)]),
    dict(key="guest_editor", name="Guest Editor", category="editorial", staff=True,
         perms=[("submissions", "*", _EDIT), ("publications", "*", _EDIT),
                ("review", "*", _CRUD)]),

    dict(key="reviewer", name="Reviewer", category="reviewer", staff=True,
         perms=[("submissions", ["submission", "submissionfile"], _VIEW),
                ("publications", ["publication"], _VIEW),
                ("review", ["reviewassignment", "reviewround", "discussion",
                            "discussionmessage"], _EDIT)]),

    dict(key="author", name="Author", category="author", staff=False,
         perms=[("submissions", ["submission", "submissionfile"], ("add", "change", "view")),
                ("publications", "*", ("add", "change", "view"))]),

    dict(key="copyeditor", name="Copyeditor", category="production", staff=True,
         perms=[("submissions", ["submission", "submissionfile"], _EDIT),
                ("publications", ["publication", "publicationtranslation"], _EDIT),
                ("review", ["discussion", "discussionmessage"], ("add", "change", "view"))]),
    dict(key="layout_editor", name="Layout Editor", category="production", staff=True,
         perms=[("publications", ["galley", "publication"], _EDIT),
                ("submissions", ["submissionfile"], _CRUD),
                ("review", ["discussion", "discussionmessage"], ("add", "change", "view"))]),
    dict(key="proofreader", name="Proofreader", category="production", staff=True,
         perms=[("submissions", ["submission"], _VIEW), ("publications", ["publication"], _VIEW),
                ("review", ["discussion", "discussionmessage"], ("add", "change", "view"))]),

    dict(key="translator", name="Translator", category="support", staff=True,
         perms=[("publications", ["publication", "publicationtranslation"], _EDIT),
                ("journals", ["journal", "section", "issue"], _EDIT),
                ("pages", ["staticpage"], _EDIT),
                ("announcements", ["announcement"], _VIEW)]),

    dict(key="designer", name="Designer", category="support", staff=True,
         perms=[("journals", ["journal"], _EDIT), ("plugins", "*", _CRUD),
                ("themes", "*", _CRUD), ("publications", ["pdftemplate"], _CRUD)]),

    dict(key="assistant", name="Journal Assistant", category="support", staff=True,
         perms=[("submissions", "*", _EDIT), ("publications", "*", _VIEW),
                ("review", ["discussion", "discussionmessage", "reviewround",
                            "reviewassignment"], ("add", "change", "view"))]),

    dict(key="subscription_manager", name="Subscription Manager", category="support",
         staff=True, perms=[("subscriptions", "*", _CRUD), ("stats", "*", _VIEW)]),

    dict(key="reader", name="Reader", category="reader", staff=False, perms=[]),
]

ROLE_BY_KEY = {r["key"]: r for r in ROLE_CATALOG}
ROLE_BY_NAME = {r["name"]: r for r in ROLE_CATALOG}

STAFF_ROLE_NAMES = {r["name"] for r in ROLE_CATALOG if r["staff"]}
EDITORIAL_ROLE_NAMES = {
    "Site Administrator", "Developer", "Journal Manager",
    "Editor", "Section Editor", "Guest Editor",
}


class Role(models.TextChoices):
    """JournalMembership / StageAssignment için (per-journal katman)."""
    SITE_ADMIN = "site_administrator", "Site Administrator"
    DEVELOPER = "developer", "Developer"
    JOURNAL_MANAGER = "journal_manager", "Journal Manager"
    EDITOR = "editor", "Editor"
    SECTION_EDITOR = "section_editor", "Section Editor"
    GUEST_EDITOR = "guest_editor", "Guest Editor"
    REVIEWER = "reviewer", "Reviewer"
    AUTHOR = "author", "Author"
    COPYEDITOR = "copyeditor", "Copyeditor"
    LAYOUT_EDITOR = "layout_editor", "Layout Editor"
    PROOFREADER = "proofreader", "Proofreader"
    TRANSLATOR = "translator", "Translator"
    DESIGNER = "designer", "Designer"
    ASSISTANT = "assistant", "Journal Assistant"
    SUBSCRIPTION_MANAGER = "subscription_manager", "Subscription Manager"
    READER = "reader", "Reader"


def _resolve_perms(spec):
    from django.contrib.auth.models import Permission
    if spec == "all":
        return Permission.objects.all()
    ids: set[int] = set()
    for app_label, mods, actions in spec:
        qs = Permission.objects.filter(content_type__app_label=app_label)
        if mods != "*":
            qs = qs.filter(content_type__model__in=mods)
        if actions != "*":
            qs = qs.filter(codename__regex=r"^(%s)_" % "|".join(actions))
        ids.update(qs.values_list("id", flat=True))
    return Permission.objects.filter(id__in=ids)


def seed_roles() -> int:
    """Tüm rolleri Group olarak oluşturur ve izinlerini atar (idempotent)."""
    from django.contrib.auth.models import Group
    for r in ROLE_CATALOG:
        group, _ = Group.objects.get_or_create(name=r["name"])
        try:
            group.permissions.set(_resolve_perms(r["perms"]))
        except Exception:
            pass
    return len(ROLE_CATALOG)
