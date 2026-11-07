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

from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .models import User


class ThrottledLoginView(LoginView):
    """5 başarısız denemeden sonra (ip/e-posta başına) 15 dk kilitleyen giriş."""

    def post(self, request, *args, **kwargs):
        from . import throttle
        username = request.POST.get("username", "")
        if throttle.is_locked(request, username):
            return render(request, "registration/login.html",
                          {"locked_out": True, "next": request.POST.get("next", "")},
                          status=429)
        return super().post(request, *args, **kwargs)


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    class Meta:
        model = User
        fields = ("email", "given_name", "family_name", "affiliation", "orcid",
                  "notify_new_issue")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


def register(request):
    from constance import config
    if not config.REGISTRATION_OPEN:
        messages.error(request, "Registration is currently closed.")
        return redirect("login")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            if getattr(config, "REQUIRE_EMAIL_VERIFICATION", False):
                user = form.save(commit=False)
                user.is_active = False
                user.save()
                _send_verification_email(user)
                return render(request, "registration/verify_sent.html",
                              {"email": user.email})
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


VERIFY_SALT = "email-verify"
VERIFY_MAX_AGE = 3 * 24 * 3600


def _send_verification_email(user) -> bool:
    from django.core import signing

    from apps.comms.services import MailService
    from apps.comms.utils import absolute_url
    from apps.journals.models import Journal

    token = signing.dumps(user.pk, salt=VERIFY_SALT)
    journal = Journal.current()
    locale = (user.preferred_locale
              if journal and user.preferred_locale in (journal.supported_locales or [])
              else (journal.primary_locale if journal else "en"))
    return MailService.send(
        "email_verification", journal=journal, locale=locale,
        to=[user.email], related=user,
        context={"journal": str(journal) if journal else "the journal",
                 "verify_url": absolute_url(f"/accounts/verify/{token}/")})


def verify_email(request, token):
    """İmzalı doğrulama linki: hesabı aktive eder ve giriş yaptırır."""
    from django.core import signing
    if request.user.is_authenticated:
        return redirect("dashboard")
    try:
        uid = signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
    except signing.SignatureExpired:
        return render(request, "registration/verify_sent.html",
                      {"expired": True}, status=410)
    except signing.BadSignature:
        from django.http import Http404
        raise Http404 from None
    user = User.objects.filter(pk=uid).first()
    if not user:
        from django.http import Http404
        raise Http404
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    login(request, user)
    messages.success(request, "Email verified — welcome!")
    return redirect("dashboard")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("given_name", "family_name", "affiliation", "affiliation_ror",
                  "orcid", "country", "biography", "preferred_locale",
                  "notify_new_issue")
        widgets = {"biography": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from apps.core.locales import locale_label
            from apps.journals.models import Journal
            j = Journal.current()
            supported = (j.supported_locales or [j.primary_locale]) if j else ["en"]
            self.fields["preferred_locale"] = forms.ChoiceField(
                choices=[(c, locale_label(c)) for c in supported],
                label="Preferred language", required=False)
        except Exception:
            pass


@login_required
def profile(request):
    prof = getattr(request.user, "reviewer_profile", None)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            if prof is not None:
                from django.utils.dateparse import parse_date
                prof.public_listing = request.POST.get("public_listing") == "on"
                prof.unavailable_until = parse_date(
                    request.POST.get("unavailable_until") or "") or None
                mx = request.POST.get("max_per_year") or ""
                prof.max_per_year = int(mx) if mx.isdigit() and int(mx) > 0 else None
                prof.save(update_fields=["public_listing", "unavailable_until",
                                         "max_per_year"])
            messages.success(request, "Profile updated.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "registration/profile.html",
                  {"form": form, "reviewer_profile": prof})


class InviteRegisterForm(forms.Form):
    given_name = forms.CharField(max_length=150, label="Given name")
    family_name = forms.CharField(max_length=150, required=False, label="Family name")
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, label="Password")


def invitation_accept(request, token):
    """Rol davetini kabul et: hesap kur (yoksa) veya mevcut hesaba rolü ekle."""
    from django.shortcuts import get_object_or_404
    from django.utils import timezone

    from .models import JournalMembership, User, UserInvitation

    inv = get_object_or_404(UserInvitation, token=token)
    ctx = {"inv": inv, "role_label": inv.get_role_display()}
    if not inv.is_valid:
        return render(request, "registration/invite.html",
                      {**ctx, "state": "invalid"}, status=410)

    def _accept(user):
        JournalMembership.objects.get_or_create(
            user=user, journal=inv.journal, role=inv.role)
        inv.accepted_at = timezone.now()
        inv.accepted_by = user
        inv.save(update_fields=["accepted_at", "accepted_by"])
        messages.success(request,
                         f"Welcome — the {inv.get_role_display()} role has been added.")
        return redirect("dashboard")

    existing = User.objects.filter(email__iexact=inv.email).first()
    if existing:
        if request.user.is_authenticated and request.user.pk == existing.pk:
            if request.method == "POST":
                return _accept(existing)
            return render(request, "registration/invite.html",
                          {**ctx, "state": "confirm"})
        return render(request, "registration/invite.html",
                      {**ctx, "state": "login_required"})

    form = InviteRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            email=inv.email, password=form.cleaned_data["password"],
            given_name=form.cleaned_data["given_name"],
            family_name=form.cleaned_data["family_name"])
        login(request, user)
        return _accept(user)
    return render(request, "registration/invite.html",
                  {**ctx, "state": "register", "form": form})
