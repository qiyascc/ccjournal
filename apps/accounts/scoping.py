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

"""Rol-tabanlı satır-seviyesi kapsam (OJS assignment-based scoping).

Model-seviyesi izinler gruplara verilir (roles.py). Bu modül *nesne-seviyesi*
kapsamı uygular: bir editör tüm gönderileri görür, ama yazar yalnız kendi
gönderilerini, hakem yalnız atandığı gönderileri görür. Superuser ve Developer
her şeyi görür.

Tasarım: tek gerçek kaynak `visible_submission_ids(user)`. Tüm submission-bağlı
admin'ler querysetlerini bu kümeye göre süzer. Böylece tutarlı ve denetlenebilir.
"""
from __future__ import annotations

FULL_SCOPE_ROLES = {
    "Site Administrator", "Developer", "Journal Manager",
    "Editor", "Section Editor", "Guest Editor",
    "Journal Assistant", "Translator",
}


def has_full_scope(user) -> bool:
    """Kullanıcı tüm gönderileri görebilir mi? (superuser/developer/editör/yönetici)"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return bool(user.role_names & FULL_SCOPE_ROLES)


def visible_submission_ids(user):
    """Kullanıcının erişebileceği Submission pk kümesi.

    Tam-kapsam rollerinde None döner (= filtre yok, hepsi). Aksi halde:
      * yazdığı/gönderdiği (submitter veya Author.email eşleşmesi)
      * hakem olarak atandığı (ReviewAssignment.reviewer)
      * aşamaya atandığı (StageAssignment.user) — copyeditor/layout vb.
      * dahil olduğu tartışmalar (Discussion.created_by / mesaj yazarı)
    """
    if has_full_scope(user):
        return None

    from apps.submissions.models import Submission
    from apps.review.models import ReviewAssignment, StageAssignment, Discussion, DiscussionMessage

    ids: set[int] = set()
    ids.update(Submission.objects.filter(submitter=user).values_list("id", flat=True))
    if user.email:
        ids.update(Submission.objects.filter(
            publications__authors__email__iexact=user.email).values_list("id", flat=True))
    ids.update(ReviewAssignment.objects.filter(reviewer=user)
               .values_list("review_round__submission_id", flat=True))
    ids.update(StageAssignment.objects.filter(user=user)
               .values_list("submission_id", flat=True))
    ids.update(Discussion.objects.filter(created_by=user)
               .values_list("submission_id", flat=True))
    ids.update(DiscussionMessage.objects.filter(author=user)
               .values_list("discussion__submission_id", flat=True))
    return ids


class ScopedAdminMixin:
    """Submission-bağlı admin'ler için satır-seviyesi süzme.

    Alt sınıf `submission_path` belirtir: queryset'ten Submission'a giden ORM yolu
    ("" = modelin kendisi Submission; "submission" = FK; "review_round__submission"…).
    """
    submission_path = ""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ids = visible_submission_ids(request.user)
        if ids is None:
            return qs
        if self.submission_path == "":
            return qs.filter(pk__in=ids)
        return qs.filter(**{f"{self.submission_path}__in": ids})

    def _obj_in_scope(self, request, obj):
        if obj is None:
            return True
        ids = visible_submission_ids(request.user)
        if ids is None:
            return True
        if self.submission_path == "":
            return obj.pk in ids
        cur = obj
        for part in self.submission_path.split("__"):
            cur = getattr(cur, part, None)
            if cur is None:
                return False
        return getattr(cur, "pk", cur) in ids

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self._obj_in_scope(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._obj_in_scope(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._obj_in_scope(request, obj)
