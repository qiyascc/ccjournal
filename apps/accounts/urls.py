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

from django.contrib.auth import views as auth_views
from django.urls import path

from . import orcid_sso, views

urlpatterns = [
    path("login/", views.ThrottledLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/accounts/login/"), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("invite/<str:token>/", views.invitation_accept, name="invitation_accept"),
    path("verify/<str:token>/", views.verify_email, name="verify_email"),
    path("orcid/login/", orcid_sso.orcid_login, name="orcid_login"),
    path("orcid/callback/", orcid_sso.orcid_callback, name="orcid_callback"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(),
         name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(),
         name="password_reset_complete"),
    path("password/change/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path("password/change/done/", auth_views.PasswordChangeDoneView.as_view(),
         name="password_change_done"),
]
