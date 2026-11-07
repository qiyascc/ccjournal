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

from django.contrib import admin
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path
from apps.themes.views import theme_css
from apps.core.health import JsonHealthCheckView
from apps.accounts.matrix import roles_matrix
from apps.review.board import board, board_columns, board_ping
from apps.review.compare import compare_reviews
from plugins.ai_assistant.views import apply_metadata as ai_apply_metadata
from plugins.ai_assistant.views import run as ai_run
from apps.review.ics import editorial_ics
from apps.submissions.files_manager import (
    download_file as manage_files_download, manage_files,
)
from apps.submissions.integrity_views import integrity_panel
from apps.submissions.dossier import dossier_pdf
from apps.web.theme_editor import theme_editor
from apps.api.metadata_proxy import funder_suggest, ror_suggest
from apps.comms.hook_views import channel_reply
from apps.comms.push_views import subscribe as push_subscribe
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.contrib.sitemaps.views import sitemap as sitemap_view
from apps.web.sitemaps import SITEMAPS
from apps.web.feeds import (
    AnnouncementsFeed, KeywordFeed, LatestArticlesAtom, LatestArticlesFeed,
    SectionFeed,
)
from apps.web.views import robots_txt

_core = [
    path("admin/otp/", __import__("apps.accounts.otp_views", fromlist=["otp_setup"]).otp_setup,
         name="otp_setup"),
    path("admin/", admin.site.urls),
    path("ckeditor5/", include("django_ckeditor_5.urls")),
    path("theme.css", theme_css, name="theme_css"),
    path("rosetta/", include("rosetta.urls")),
    path("health/", JsonHealthCheckView.as_view(), name="health"),
    path("api/v1/", include("apps.api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("reports/", include("apps.reports.urls")),
    path("hijack/", include("hijack.urls")),
    path("manage/roles/", roles_matrix, name="roles_matrix"),
    path("manage/board/", board, name="board"),
    path("manage/board/columns/", board_columns, name="board_columns"),
    path("manage/board/ping/", board_ping, name="board_ping"),
    path("manage/files/<int:pk>/", manage_files, name="manage_files"),
    path("manage/files/<int:pk>/dl/<int:file_id>/", manage_files_download,
         name="manage_files_download"),
    path("manage/reviews/<int:pk>/", compare_reviews, name="manage_reviews"),
    path("manage/ai/run/<slug:kind>/<int:pk>/", ai_run, name="ai_run"),
    path("manage/ai/apply-metadata/<int:pk>/", ai_apply_metadata,
         name="ai_apply_metadata"),
    path("manage/integrity/<int:pk>/", integrity_panel, name="manage_integrity"),
    path("manage/dossier/<int:pk>.pdf", dossier_pdf, name="manage_dossier"),
    path("manage/theme/", theme_editor, name="theme_editor"),
    path("manage/calendar/<str:token>/editorial.ics", editorial_ics,
         name="editorial_ics"),
    path("api/suggest/ror", ror_suggest, name="ror_suggest"),
    path("api/suggest/funder", funder_suggest, name="funder_suggest"),
    path("push/subscribe/", push_subscribe, name="push_subscribe"),
    path("hooks/channel-reply/", channel_reply, name="channel_reply"),
    path("sitemap.xml", sitemap_view, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path("feed/", LatestArticlesFeed(), name="feed"),
    path("feed/atom/", LatestArticlesAtom(), name="feed_atom"),
    path("feed/announcements/", AnnouncementsFeed(), name="feed_announcements"),
    path("feed/section/<int:pk>/", SectionFeed(), name="feed_section"),
    path("feed/keyword/<str:term>/", KeywordFeed(), name="feed_keyword"),
    path("", include("apps.metadata.urls")),
]

from apps.web.dashboard import dashboard as user_dashboard  # noqa: E402

_public = [
    path("forms/", include("apps.formbuilder.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", user_dashboard, name="dashboard"),
    path("submit/", include("apps.submissions.urls")),
    path("review/", include("apps.review.public_urls")),
    path("work/", include("apps.submissions.author_urls")),
    path("", include("apps.web.urls")),
]

if getattr(settings, "LANGUAGE_URL_TYPE", "query") == "slug":
    urlpatterns = _core + i18n_patterns(*_public, prefix_default_language=False)
else:
    urlpatterns = _core + _public
