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

from django.urls import path

from . import citations, views
from .cards import article_card
from apps.comms.newsletter_views import (
    newsletter, newsletter_confirm, newsletter_unsubscribe,
)

app_name = "web"

urlpatterns = [
    path("setup/", views.setup, name="setup"),
    path("page/<slug:slug>/", views.page, name="page"),
    path("", views.home, name="home"),
    path("issues/", views.issue_archive, name="archive"),
    path("issue/<int:pk>/", views.issue_detail, name="issue"),
    path("issue/<int:pk>/galley/", views.issue_galley, name="issue_galley"),
    path("article/<int:pk>/", views.article, name="article"),
    path("article/<int:pk>/cite.bib", citations.cite_bibtex, name="cite_bibtex"),
    path("article/<int:pk>/cite.ris", citations.cite_ris, name="cite_ris"),
    path("article/<int:pk>/jats.xml", citations.article_jats, name="article_jats"),
    path("article/<int:pk>/card.png", article_card, name="article_card"),
    path("article/<int:pk>/galley/<int:galley_id>/", views.galley, name="galley"),
    path("article/<int:pk>/view/<int:galley_id>/", views.galley_view, name="galley_view"),
    path("section/<int:pk>/", views.section_browse, name="section"),
    path("search/", views.search, name="search"),
    path("reviewers/", views.reviewers_page, name="reviewers"),
    path("most-cited/", views.most_cited, name="most_cited"),
    path("keyword/<str:term>/", views.keyword_browse, name="keyword"),
    path("author/<int:pk>/", views.author_browse, name="author"),
    path("calls/", views.calls_page, name="calls"),
    path("accessibility/", views.accessibility, name="accessibility"),
    path("newsletter/", newsletter, name="newsletter"),
    path("newsletter/confirm/<str:token>/", newsletter_confirm,
         name="newsletter_confirm"),
    path("newsletter/unsubscribe/<str:token>/", newsletter_unsubscribe,
         name="newsletter_unsubscribe"),
    path("announcements/", views.announcements, name="announcements"),
    path("announcement/<int:pk>/", views.announcement_detail, name="announcement"),
    path("categories/", views.categories, name="categories"),
    path("category/<slug:slug>/", views.category_browse, name="category"),
]
