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

"""RSS/Atom — son makaleler ve duyurular."""
from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed


def _journal():
    from apps.journals.models import Journal
    return Journal.current()


def _jtitle():
    j = _journal()
    if not j:
        return "Journal"
    t = j.tr()
    if t and t.title:
        return t.title
    row = j.translations.first()
    return row.title if row else "Journal"


class LatestArticlesFeed(Feed):
    def title(self):
        return f"{_jtitle()} — Latest articles"

    def link(self):
        return reverse("web:home")

    def description(self):
        return "Most recent peer-reviewed articles."

    def items(self):
        from apps.submissions.models import Submission, SubmissionStatus
        return (Submission.objects.filter(status=SubmissionStatus.PUBLISHED)
                .select_related("current_publication")
                .order_by("-current_publication__date_published")[:20])

    def item_title(self, obj):
        p = obj.current_publication
        t = p.tr(obj.locale) if p else None
        return t.title if t else f"Article #{obj.pk}"

    def item_description(self, obj):
        p = obj.current_publication
        t = p.tr(obj.locale) if p else None
        return (t.abstract or "")[:500] if t else ""

    def item_link(self, obj):
        return reverse("web:article", args=[obj.pk])

    def item_pubdate(self, obj):
        from datetime import datetime, time
        p = obj.current_publication
        d = getattr(p, "date_published", None)
        return datetime.combine(d, time.min) if d else None


class LatestArticlesAtom(LatestArticlesFeed):
    feed_type = Atom1Feed
    subtitle = LatestArticlesFeed.description


class AnnouncementsFeed(Feed):
    def title(self):
        return f"{_jtitle()} — Announcements"

    def link(self):
        return reverse("web:announcements")

    def description(self):
        return "Journal announcements."

    def items(self):
        from apps.announcements.models import Announcement
        return Announcement.objects.filter(is_published=True)[:20]

    def item_title(self, obj):
        t = obj.tr()
        return t.title if t else f"Announcement #{obj.pk}"

    def item_description(self, obj):
        t = obj.tr()
        return (getattr(t, "short_description", "") or getattr(t, "body", "") or "")[:500] if t else ""

    def item_link(self, obj):
        return reverse("web:announcement", args=[obj.pk])


class SectionFeed(LatestArticlesFeed):
    """Bölüm bazlı RSS — /feed/section/<pk>/."""

    def get_object(self, request, pk):
        from apps.journals.models import Section
        return Section.objects.get(pk=pk, journal=_journal())

    def title(self, obj):
        return f"{_jtitle()} — {obj.tr_value('title') or 'Section'}"

    def link(self, obj):
        return f"/section/{obj.pk}/"

    def items(self, obj):
        from apps.submissions.models import Submission, SubmissionStatus
        return (Submission.objects
                .filter(status=SubmissionStatus.PUBLISHED,
                        current_publication__section=obj)
                .select_related("current_publication")
                .order_by("-current_publication__date_published")[:20])


class KeywordFeed(LatestArticlesFeed):
    """Anahtar kelime bazlı RSS — /feed/keyword/<term>/."""

    def get_object(self, request, term):
        return term

    def title(self, obj):
        return f"{_jtitle()} — “{obj}”"

    def link(self, obj):
        from urllib.parse import quote
        return f"/keyword/{quote(obj)}/"

    def items(self, obj):
        from apps.submissions.models import Submission, SubmissionStatus
        return (Submission.objects
                .filter(status=SubmissionStatus.PUBLISHED,
                        current_publication__keywords__term__iexact=obj)
                .select_related("current_publication").distinct()
                .order_by("-current_publication__date_published")[:20])
