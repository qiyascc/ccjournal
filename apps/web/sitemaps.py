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

"""sitemap.xml — makaleler, sayılar, statik sayfalar, duyurular, kategoriler."""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class _Base(Sitemap):
    protocol = "https"


class ArticleSitemap(_Base):
    changefreq = "monthly"
    priority = 0.9

    def items(self):
        from apps.submissions.models import Submission, SubmissionStatus
        return (Submission.objects.filter(status=SubmissionStatus.PUBLISHED)
                .select_related("current_publication").order_by("-id"))

    def location(self, obj):
        return reverse("web:article", args=[obj.pk])

    def lastmod(self, obj):
        p = obj.current_publication
        return getattr(p, "date_published", None)


class IssueSitemap(_Base):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        from apps.journals.models import Issue
        return Issue.objects.filter(is_published=True)

    def location(self, obj):
        return reverse("web:issue", args=[obj.pk])

    def lastmod(self, obj):
        return obj.date_published


class PageSitemap(_Base):
    changefreq = "yearly"
    priority = 0.5

    def items(self):
        from apps.pages.models import StaticPage
        return StaticPage.objects.filter(is_published=True, robots_noindex=False)

    def location(self, obj):
        return reverse("web:page", args=[obj.slug])


class AnnouncementSitemap(_Base):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        from apps.announcements.models import Announcement
        return Announcement.objects.filter(is_published=True)

    def location(self, obj):
        return reverse("web:announcement", args=[obj.pk])


class StaticViewSitemap(_Base):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["web:home", "web:archive", "web:search",
                "web:announcements", "web:categories"]

    def location(self, name):
        return reverse(name)


SITEMAPS = {
    "static": StaticViewSitemap, "articles": ArticleSitemap, "issues": IssueSitemap,
    "pages": PageSitemap, "announcements": AnnouncementSitemap,
}
