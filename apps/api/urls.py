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

"""API router — /api/v1/ altında tüm kaynaklar + OpenAPI şema/docs."""
from rest_framework.routers import DefaultRouter

from . import views as v
from .permissions import PublicReadRoleWrite, RoleModelPermissions
from .views import make_viewset, public_viewset

from apps.journals.models import (
    Category, CategoryTranslation, ChecklistItem, ChecklistItemTranslation, IssueTranslation, Journal, JournalTranslation, Section, SectionTranslation,
)
from apps.publications.models import (
    Author, Citation, Funding, Galley, Keyword, PublicationTranslation, Subject,
)
from apps.submissions.models import Genre, SubmissionFile
from apps.review.models import (
    Discussion, DiscussionMessage, EditorialDecision, ReviewAssignment, ReviewerProfile,
    ReviewInterest, ReviewRound, StageAssignment,
)
from apps.comms.models import EmailLog, EmailTemplate
from apps.subscriptions.models import Payment, Subscription, SubscriptionType
from apps.pages.models import StaticPage, StaticPageTranslation
from apps.navigation.models import MenuItem
from apps.configuration.models import ConfigSetting
from apps.stats.models import MetricDay
from apps.announcements.models import Announcement, AnnouncementTranslation

router = DefaultRouter()

router.register("submissions", v.submission_viewset(), basename="submission")
router.register("publications", v.publication_viewset(), basename="publication")
router.register("issues", v.issue_viewset(), basename="issue")
router.register("users", v.UserViewSet, basename="user")
router.register("api-keys", v.ApiKeyViewSet, basename="apikey")

PUB = PublicReadRoleWrite
for model, route, pubfilter, search in [
    (Journal, "journals", None, []),
    (Section, "sections", None, []),
    (Category, "categories", None, ["slug"]),
    (Announcement, "announcements", {"is_published": True}, []),
]:
    router.register(route, public_viewset(model, published_filter=pubfilter, search=search),
                    basename=route)

PROT = RoleModelPermissions
_protected = [
    (Author, "authors", ["family_name", "given_name"]),
    (Keyword, "keywords", ["term"]),
    (Subject, "subjects", []),
    (Citation, "citations", []),
    (Funding, "funding", []),
    (Galley, "galleys", []),
    (Genre, "genres", []),
    (SubmissionFile, "submission-files", []),
    (ReviewRound, "review-rounds", []),
    (ReviewAssignment, "review-assignments", []),
    (EditorialDecision, "editorial-decisions", []),
    (StageAssignment, "stage-assignments", []),
    (Discussion, "discussions", []),
    (DiscussionMessage, "discussion-messages", []),
    (ReviewerProfile, "reviewer-profiles", []),
    (ReviewInterest, "review-interests", ["name"]),
    (EmailTemplate, "email-templates", ["key"]),
    (EmailLog, "email-log", ["subject", "to_emails"]),
    (SubscriptionType, "subscription-types", ["name"]),
    (Subscription, "subscriptions", []),
    (Payment, "payments", []),
    (StaticPage, "pages", ["slug"]),
    (MenuItem, "menu-items", []),
    (ConfigSetting, "config", ["section", "key"]),
    (MetricDay, "metrics", []),
    (ChecklistItem, "checklist-items", []),
    (JournalTranslation, "journal-translations", []),
    (SectionTranslation, "section-translations", []),
    (IssueTranslation, "issue-translations", []),
    (CategoryTranslation, "category-translations", []),
    (PublicationTranslation, "publication-translations", []),
    (StaticPageTranslation, "page-translations", []),
    (AnnouncementTranslation, "announcement-translations", []),
    (ChecklistItemTranslation, "checklist-translations", []),
]
for model, route, search in _protected:
    router.register(route, make_viewset(model, permission=PROT, search=search), basename=route)

urlpatterns = router.urls
