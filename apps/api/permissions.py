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

"""Rol-tabanlı izinler — OJS gibi, anahtar sahibinin yetkilerine göre."""
from rest_framework.permissions import (
    BasePermission, DjangoModelPermissions, IsAuthenticated,
)


class RoleModelPermissions(DjangoModelPermissions):
    """Django model izinleri; GET için de 'view' izni şart (hassas kaynaklar)."""
    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [], "HEAD": [],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }


class PublicReadRoleWrite(DjangoModelPermissions):
    """Herkese okuma; yazma için rol izni (public içerik kaynakları)."""
    authenticated_users_only = False
    perms_map = {
        "GET": [], "OPTIONS": [], "HEAD": [],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }


class SubmissionPermission(BasePermission):
    """Yazar kendi gönderisini; editör/staff hepsini yönetir."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        u = request.user
        if u.is_staff:
            return True
        owner_id = getattr(obj, "submitter_id", None)
        if owner_id is None and hasattr(obj, "submission"):
            owner_id = getattr(obj.submission, "submitter_id", None)
        return owner_id == u.id


class IsOwnerOfApiKey(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id
