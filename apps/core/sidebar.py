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

"""Unfold sidebar — TÜM kayıtlı modeller, açılır-kapanır başlıklar altında.

Her grup `collapsible: True` (başlığa tıklayınca açılır/kapanır; içinde aktif
sayfa varsa otomatik açık gelir). Yalnız model değil, admin-dışı yönetim
yüzeyleri de (Tools) burada.
"""
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


def _a(label, model):
    return reverse_lazy(f"admin:{label}_{model}_changelist")


import re as _re
_CL_RE = _re.compile(r"admin:(?P<app>\w+)_(?P<model>\w+)_changelist")


def _perm_for_link(link):
    """Bir sidebar item için (request)->bool izin callable'ı döndürür.

    Link bir reverse_lazy olabilir; string'e çevirme (ve dolayısıyla URL çözümleme)
    yalnız callback çağrıldığında yapılır — settings import anında apps hazır değil.
    """
    def _check(request):
        u = getattr(request, "user", None)
        if not u or not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        s = str(link)
        m = _CL_RE.search(s) or _re.search(r"/admin/(?P<app>\w+)/(?P<model>\w+)/", s)
        if m:
            return u.has_perm(f"{m.group('app')}.view_{m.group('model')}")
        roles = u.role_names
        if s.startswith("/rosetta"):
            return bool(roles & {"Translator", "Journal Manager"})
        if "themes_installedtheme_install" in s:
            return "Designer" in roles
        if s.startswith("/api/docs"):
            return False
        if "reports" in s:
            return bool(roles & {"Journal Manager", "Editor", "Subscription Manager"})
        return bool(u.is_staff)
    return _check


def _wrap_permissions(nav):
    """Her item'a otomatik `permission` ekler; tüm item'ları gizliyse grubu da gizler."""
    for group in nav:
        for item in group.get("items", []):
            if "permission" not in item and "link" in item:
                item["permission"] = _perm_for_link(item["link"])
    return nav


def build_navigation():
    return _wrap_permissions(_build_navigation_raw())


def _build_navigation_raw():
    return [
        {
            "title": _("Editorial"),
            "collapsible": True,
            "items": [
                {"title": _("Dashboard"), "icon": "dashboard",
                 "link": reverse_lazy("admin:index")},
                {"title": _("Submissions"), "icon": "inbox",
                 "link": _a("submissions", "submission")},
                {"title": _("Publications"), "icon": "article",
                 "link": _a("publications", "publication")},
                {"title": _("Issues"), "icon": "menu_book",
                 "link": _a("journals", "issue")},
                {"title": _("Genres (file types)"), "icon": "folder_open",
                 "link": _a("submissions", "genre")},
            ],
        },
        {
            "title": _("Peer review"),
            "collapsible": True,
            "items": [
                {"title": _("Review rounds"), "icon": "loop",
                 "link": _a("review", "reviewround")},
                {"title": _("Review assignments"), "icon": "rate_review",
                 "link": _a("review", "reviewassignment")},
                {"title": _("Editorial decisions"), "icon": "gavel",
                 "link": _a("review", "editorialdecision")},
                {"title": _("Stage assignments"), "icon": "assignment_ind",
                 "link": _a("review", "stageassignment")},
                {"title": _("Discussions"), "icon": "forum",
                 "link": _a("review", "discussion")},
                {"title": _("Reviewer pool"), "icon": "diversity_3",
                 "link": _a("review", "reviewerprofile")},
                {"title": _("Review interests"), "icon": "interests",
                 "link": _a("review", "reviewinterest")},
            ],
        },
        {
            "title": _("Content & site"),
            "collapsible": True,
            "items": [
                {"title": _("Journal"), "icon": "settings_applications",
                 "link": _a("journals", "journal")},
                {"title": _("Sections"), "icon": "category",
                 "link": _a("journals", "section")},
                {"title": _("Categories"), "icon": "account_tree",
                 "link": _a("journals", "category")},
                {"title": _("Checklist items"), "icon": "checklist",
                 "link": _a("journals", "checklistitem")},
                {"title": _("Static pages"), "icon": "description",
                 "link": _a("pages", "staticpage")},
                {"title": _("Announcements"), "icon": "campaign",
                 "link": _a("announcements", "announcement")},
                {"title": _("Forms"), "icon": "dynamic_form",
                 "link": _a("formbuilder", "form")},
                {"title": _("Form submissions"), "icon": "move_to_inbox",
                 "link": _a("formbuilder", "formsubmission")},
                {"title": _("Navigation (menus & footer)"), "icon": "menu",
                 "link": _a("navigation", "menuitem")},
                {"title": _("Themes"), "icon": "palette",
                 "link": _a("themes", "installedtheme")},
                {"title": _("PDF templates"), "icon": "picture_as_pdf",
                 "link": _a("publications", "pdftemplate")},
                {"title": _("DOIs (Crossref)"), "icon": "fingerprint",
                 "link": _a("core", "doi")},
                {"title": _("Tombstones (OAI deleted)"), "icon": "delete_history",
                 "link": _a("metadata", "tombstone")},
            ],
        },
        {
            "title": _("Communication"),
            "collapsible": True,
            "items": [
                {"title": _("Email templates"), "icon": "mail",
                 "link": _a("comms", "emailtemplate")},
                {"title": _("Email log"), "icon": "outgoing_mail",
                 "link": _a("comms", "emaillog")},
                {"title": _("Notifications"), "icon": "notifications",
                 "link": _a("comms", "notification")},
                {"title": _("Web push devices"), "icon": "devices",
                 "link": _a("push_notifications", "webpushdevice")},
                {"title": _("APNS devices"), "icon": "phone_iphone",
                 "link": _a("push_notifications", "apnsdevice")},
                {"title": _("FCM devices"), "icon": "smartphone",
                 "link": _a("push_notifications", "gcmdevice")},
                {"title": _("WNS devices"), "icon": "laptop_windows",
                 "link": _a("push_notifications", "wnsdevice")},
            ],
        },
        {
            "title": _("People & access"),
            "collapsible": True,
            "items": [
                {"title": _("Users"), "icon": "person",
                 "link": _a("accounts", "user")},
                {"title": _("Roles (groups)"), "icon": "groups",
                 "link": _a("auth", "group")},
                {"title": _("Role matrix"), "icon": "grid_on",
                 "link": reverse_lazy("roles_matrix")},
                {"title": _("Journal memberships"), "icon": "badge",
                 "link": _a("accounts", "journalmembership")},
                {"title": _("API keys"), "icon": "key",
                 "link": _a("accounts", "apikey")},
            ],
        },
        {
            "title": _("Subscriptions"),
            "collapsible": True,
            "items": [
                {"title": _("Subscription types"), "icon": "sell",
                 "link": _a("subscriptions", "subscriptiontype")},
                {"title": _("Subscriptions"), "icon": "card_membership",
                 "link": _a("subscriptions", "subscription")},
                {"title": _("Payments"), "icon": "payments",
                 "link": _a("subscriptions", "payment")},
            ],
        },
        {
            "title": _("System"),
            "collapsible": True,
            "items": [
                {"title": _("Configuration (config.ini)"), "icon": "tune",
                 "link": _a("configuration", "configsetting")},
                {"title": _("Runtime settings"), "icon": "settings_suggest",
                 "link": _a("constance", "config")},
                {"title": _("Plugins"), "icon": "extension",
                 "link": _a("plugins", "pluginstate")},
                {"title": _("Plugin settings"), "icon": "settings_input_component",
                 "link": _a("plugins", "pluginsetting")},
                {"title": _("Feature flags"), "icon": "flag",
                 "link": _a("waffle", "flag")},
                {"title": _("Switches"), "icon": "toggle_on",
                 "link": _a("waffle", "switch")},
                {"title": _("Samples"), "icon": "percent",
                 "link": _a("waffle", "sample")},
                {"title": _("Audit log"), "icon": "history",
                 "link": _a("auditlog", "logentry")},
                {"title": _("Metrics (daily)"), "icon": "monitoring",
                 "link": _a("stats", "metricday")},
                {"title": _("Reports (CSV)"), "icon": "summarize",
                 "link": reverse_lazy("reports:index")},
            ],
        },
        {
            "title": _("Tools"),
            "collapsible": True,
            "separator": True,
            "items": [
                {"title": _("Translations (Rosetta)"), "icon": "translate",
                 "link": "/rosetta/"},
                {"title": _("Install theme (.zip)"), "icon": "upload",
                 "link": reverse_lazy("admin:themes_installedtheme_install")},
                {"title": _("API docs (Swagger)"), "icon": "api",
                 "link": "/api/docs/"},
                {"title": _("OAI-PMH endpoint"), "icon": "hub",
                 "link": "/oai?verb=Identify"},
                {"title": _("Sitemap"), "icon": "map", "link": "/sitemap.xml"},
                {"title": _("RSS feed"), "icon": "rss_feed", "link": "/feed/"},
                {"title": _("Health check"), "icon": "monitor_heart",
                 "link": "/health/"},
                {"title": _("View site"), "icon": "public", "link": "/"},
            ],
        },
    ]
