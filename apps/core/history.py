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
Merkezî simple-history kaydı — model dosyalarını düzenlemeden tüm anlamlı modellere
sürümlü geçmiş ekler. Yüksek-churn/ephemeral modeller hariç (auditlog onları kaplar).
"""
from __future__ import annotations

from simple_history import register

_DONE = False


def register_history():
    global _DONE
    if _DONE:
        return
    _DONE = True

    from apps.accounts.models import JournalMembership, User
    from apps.journals.models import (
        Category, CategoryTranslation, ChecklistItem, ChecklistItemTranslation, Issue,
        IssueTranslation, Journal, JournalTranslation, Section, SectionTranslation,
    )
    from apps.submissions.models import Genre, Submission, SubmissionFile
    from apps.publications.models import (
        Author, Citation, Funding, Galley, Keyword, Publication, PublicationTranslation, Subject,
    )
    from apps.review.models import (
        Discussion, DiscussionMessage, EditorialDecision, ReviewAssignment, ReviewRound,
        ReviewerProfile, StageAssignment,
    )
    from apps.comms.models import EmailTemplate
    from apps.pages.models import StaticPage, StaticPageTranslation
    from apps.navigation.models import MenuItem, MenuItemLabel
    from apps.themes.models import InstalledTheme
    from apps.configuration.models import ConfigSetting
    from apps.announcements.models import Announcement, AnnouncementTranslation
    from apps.subscriptions.models import Payment, Subscription, SubscriptionType

    models = [
        User, JournalMembership,
        Journal, JournalTranslation, Section, SectionTranslation, Issue, IssueTranslation,
        Category, CategoryTranslation, ChecklistItem, ChecklistItemTranslation,
        Submission, SubmissionFile, Genre,
        Publication, PublicationTranslation, Author, Keyword, Subject, Citation, Funding, Galley,
        ReviewRound, ReviewAssignment, EditorialDecision, StageAssignment, Discussion, DiscussionMessage,
        ReviewerProfile,
        EmailTemplate, StaticPage, StaticPageTranslation, MenuItem, MenuItemLabel,
        InstalledTheme, ConfigSetting, Announcement, AnnouncementTranslation,
        SubscriptionType, Subscription, Payment,
    ]
    for m in models:
        try:
            register(m)
        except Exception:
            pass
