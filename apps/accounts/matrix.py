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

"""OJS-vari Rol × Yetki matrisi — satır=rol (Group), sütun=yetki; onay kutulu, düzenlenebilir.
Yalnız superuser ve Developer rolü erişip kaydedebilir."""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

MATRIX_MODELS = [
    ("submissions", "submission"), ("publications", "publication"),
    ("journals", "issue"), ("journals", "section"), ("journals", "category"),
    ("announcements", "announcement"), ("review", "reviewassignment"),
    ("review", "editorialdecision"), ("accounts", "user"),
    ("comms", "emailtemplate"), ("subscriptions", "subscription"),
    ("pages", "staticpage"), ("navigation", "menuitem"),
    ("themes", "installedtheme"), ("plugins", "pluginstate"),
    ("configuration", "configsetting"),
    ("formbuilder", "form"), ("formbuilder", "formsubmission"),
]
ACTIONS = ["view", "add", "change", "delete"]


def _can_edit(user):
    return bool(user.is_authenticated and (
        user.is_superuser or user.groups.filter(name="Developer").exists()))


def _matrix_permissions():
    """Sütun düzeni: [(model_label, [(perm, action), x4]), ...] + düz perm id listesi."""
    cols, all_ids = [], []
    for app_label, model in MATRIX_MODELS:
        ct = ContentType.objects.filter(app_label=app_label, model=model).first()
        if not ct:
            continue
        perms = []
        for act in ACTIONS:
            p = Permission.objects.filter(
                content_type=ct, codename=f"{act}_{model}").first()
            if p:
                perms.append((p, act))
                all_ids.append(p.id)
        if perms:
            label = ct.model_class()._meta.verbose_name.title() if ct.model_class() else model
            cols.append({"model": label, "perms": perms})
    return cols, all_ids


def roles_matrix(request):
    if not _can_edit(request.user):
        return HttpResponseForbidden("Only superusers and Developers may edit the role matrix.")
    cols, all_ids = _matrix_permissions()
    groups = list(Group.objects.all().order_by("name"))

    if request.method == "POST":
        for g in groups:
            checked = set()
            for pid in all_ids:
                if request.POST.get(f"perm_{g.id}_{pid}"):
                    checked.add(pid)
            current = set(g.permissions.filter(id__in=all_ids).values_list("id", flat=True))
            to_add = checked - current
            to_remove = current - checked
            if to_add:
                g.permissions.add(*to_add)
            if to_remove:
                g.permissions.remove(*to_remove)
        messages.success(request, "Role permissions updated.")
        return redirect("roles_matrix")

    group_rows = []
    for g in groups:
        owned = set(g.permissions.filter(id__in=all_ids).values_list("id", flat=True))
        group_rows.append({"group": g, "owned": owned})
    return render(request, "admin/roles_matrix.html", {
        "cols": cols, "group_rows": group_rows, "actions": ACTIONS,
        "title": "Role permission matrix",
    })
