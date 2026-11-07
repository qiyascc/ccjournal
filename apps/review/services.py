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
Değerlendirme + editöryal akış iş kuralları.

WorkflowService.record_decision: editöryal kararı kaydeder VE gönderinin aşama/durum
geçişini yapar (OJS EditorialDecision sonrası stage transition'ları).
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.submissions.models import Stage, Submission, SubmissionStatus
from .models import EditorialDecision, ReviewAssignment, ReviewRound

logger = logging.getLogger("ccjournal.review")


class ReviewService:
    @staticmethod
    @transaction.atomic
    def assign_reviewer(review_round: ReviewRound, reviewer, *, due=None, mode=None) -> ReviewAssignment:
        mode = mode or review_round.submission.journal.default_review_mode
        assignment, created = ReviewAssignment.objects.get_or_create(
            review_round=review_round, reviewer=reviewer,
            defaults={"review_mode": mode, "date_due": due},
        )
        if review_round.status == ReviewRound.Status.PENDING:
            review_round.status = ReviewRound.Status.IN_REVIEW
            review_round.save(update_fields=["status"])
        if created:
            from apps.comms.services import review_assigned
            review_assigned.send(sender=ReviewAssignment, assignment=assignment)
        return assignment

    @staticmethod
    def submit_review(assignment: ReviewAssignment, *, recommendation,
                      comments_for_editor="", comments_for_author="",
                      competing_interests="") -> ReviewAssignment:
        assignment.recommendation = recommendation
        assignment.comments_for_editor = comments_for_editor
        assignment.comments_for_author = comments_for_author
        assignment.competing_interests = competing_interests
        assignment.date_completed = timezone.now()
        assignment.save()
        return assignment

    @staticmethod
    def decline_review(assignment: ReviewAssignment) -> ReviewAssignment:
        assignment.declined = True
        assignment.save(update_fields=["declined"])
        return assignment


class WorkflowService:
    @staticmethod
    def ensure_review_round(submission: Submission, stage: int = Stage.REVIEW) -> ReviewRound:
        """Açık bir round varsa onu döndürür; yoksa yeni round açar."""
        last = submission.review_rounds.filter(stage=stage).order_by("-round").first()
        terminal = {ReviewRound.Status.ACCEPTED, ReviewRound.Status.DECLINED}
        if last and last.status not in terminal:
            return last
        next_no = (last.round + 1) if last else 1
        return ReviewRound.objects.create(submission=submission, stage=stage, round=next_no)

    @staticmethod
    @transaction.atomic
    def record_decision(submission: Submission, editor, decision: int, *,
                        note: str = "", review_round: ReviewRound | None = None,
                        notify_author: bool = True) -> EditorialDecision:
        """Kararı kaydeder + gönderi aşama/durum geçişini uygular.

        notify_author=False: otomatik yazar E-POSTASI bastırılır (in-app bildirim
        kalır) — editör e-postayı önizleyip düzenleyerek kendisi gönderecektir.
        """
        ed = EditorialDecision.objects.create(
            submission=submission, editor=editor, decision=decision,
            stage=submission.stage, review_round=review_round, note=note,
        )
        D = EditorialDecision.Decision

        if decision == D.SEND_TO_REVIEW:
            submission.stage = Stage.REVIEW
            WorkflowService.ensure_review_round(submission)
        elif decision in (D.DECLINE, D.INITIAL_DECLINE):
            submission.status = SubmissionStatus.DECLINED
        elif decision == D.ACCEPT:
            submission.stage = Stage.EDITING
            if review_round:
                review_round.status = ReviewRound.Status.ACCEPTED
                review_round.save(update_fields=["status"])
        elif decision == D.SEND_TO_COPYEDIT:
            submission.stage = Stage.EDITING
        elif decision == D.SEND_TO_PRODUCTION:
            submission.stage = Stage.PRODUCTION
        elif decision in (D.PENDING_REVISIONS, D.RESUBMIT):
            rnd = review_round or submission.review_rounds.order_by("-round").first()
            if rnd:
                rnd.status = ReviewRound.Status.REVISIONS
                rnd.save(update_fields=["status"])

        submission.save(update_fields=["stage", "status", "date_status_modified"])
        from apps.comms.services import decision_recorded
        decision_recorded.send(sender=EditorialDecision, decision=ed,
                               notify_author=notify_author)

        author_actions = {
            D.SEND_TO_COPYEDIT: "copyedit", D.SEND_TO_PRODUCTION: "proof",
        }
        if decision in author_actions:
            WorkflowService._notify_author(submission, author_actions[decision],
                                           email=notify_author)
        return ed

    @staticmethod
    def _notify_author(submission, kind: str, *, email: bool = True):
        """Yazara in-app bildirim (+ istenirse e-posta); token'lı çalışma alanı linki."""
        author = submission.submitter
        if not author:
            return
        work_url = f"/work/{submission.author_token}/"
        titles = {"revision": "Revisions requested",
                  "copyedit": "Your article is in copyediting",
                  "proof": "Proof ready for your review"}
        title = titles.get(kind, "Action required on your submission")
        try:
            from apps.comms.services import NotifyService
            NotifyService.create(author, "author_action", title,
                                 journal=submission.journal, url=work_url)
        except Exception:
            logger.warning("author in-app notification failed (submission %s)",
                           submission.pk, exc_info=True)
        try:
            if email and author.email:
                from apps.comms.utils import absolute_url
                from apps.tasks.queue import enqueue_or_run
                enqueue_or_run("apps.comms.tasks.send_author_action_email",
                               submission.id, title, kind, absolute_url(work_url))
        except Exception:
            logger.warning("author email notification failed (submission %s)",
                           submission.pk, exc_info=True)
        return


class ReviewerService:
    """Hakem havuzu: ilgi alanı/aramaya göre filtreli + istatistikli profil listesi."""

    @staticmethod
    def pool(*, q: str | None = None, interest_id=None, available_only: bool = False):
        from django.db.models import Avg, Count, Q
        from .models import ReviewerProfile

        qs = (ReviewerProfile.objects.select_related("user")
              .prefetch_related("interests", "user__review_assignments"))
        if available_only:
            from django.db.models import Q as _Q
            from django.utils import timezone as _tz
            qs = qs.filter(is_available=True).filter(
                _Q(unavailable_until__isnull=True)
                | _Q(unavailable_until__lt=_tz.localdate()))
        if interest_id:
            qs = qs.filter(interests__id=interest_id)
        if q:
            qs = qs.filter(
                Q(user__email__icontains=q) | Q(user__given_name__icontains=q)
                | Q(user__family_name__icontains=q) | Q(affiliation__icontains=q)
                | Q(expertise__icontains=q) | Q(interests__name__icontains=q))
        qs = qs.annotate(
            n_assigned=Count("user__review_assignments", distinct=True),
            n_completed=Count("user__review_assignments",
                              filter=Q(user__review_assignments__date_completed__isnull=False),
                              distinct=True),
            n_declined=Count("user__review_assignments",
                             filter=Q(user__review_assignments__declined=True), distinct=True),
            avg_quality=Avg("user__review_assignments__quality"),
        )
        return qs.distinct()

    @staticmethod
    def ensure_profile(user):
        from .models import ReviewerProfile
        prof, _ = ReviewerProfile.objects.get_or_create(user=user)
        return prof
