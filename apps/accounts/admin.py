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
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from hijack.contrib.admin import HijackUserAdminMixin

from .models import JournalMembership, User, ApiKey, UserInvitation


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "given_name", "groups")


class MembershipInline(TabularInline):
    model = JournalMembership
    extra = 1
    tab = True
    autocomplete_fields = ("journal",)


@admin.register(User)
class UserAdmin(HijackUserAdminMixin, BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreateForm
    change_password_form = AdminPasswordChangeForm
    inlines = [MembershipInline]

    ordering = ("email",)
    list_display = ("email", "full_name", "roles_display", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("email", "given_name", "family_name", "orcid")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("given_name", "family_name", "preferred_locale", "biography")}),
        ("Scholarly identity", {"fields": ("orcid", "affiliation", "affiliation_ror", "country")}),
        ("Roles & permissions", {"fields": ("is_active", "is_staff", "is_superuser",
                                            "groups", "user_permissions")}),
    )

    def get_fieldsets(self, request, obj=None):
        """WhatsApp numarası alanı yalnız WhatsApp plugin'i etkinse görünür.

        Plugin kapalıyken alan gizlenir; veritabanındaki numaralar korunur
        (silinmez), plugin tekrar açılınca yeniden görünür.
        """
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None:
            return fieldsets
        try:
            from apps.plugins.registry import registry
            if registry.is_enabled("whatsapp"):
                fieldsets = list(fieldsets) + [
                    ("WhatsApp", {"fields": ("whatsapp_number",),
                                  "description": "International format, e.g. 994501234567. "
                                  "Notifications are also delivered to this number via WhatsApp."})]
            if registry.is_enabled("telegram"):
                fieldsets = list(fieldsets) + [
                    ("Telegram", {"fields": ("telegram_id", "telegram_username", "telegram_start_link"),
                                  "description": "Linked automatically when the user connects the bot. "
                                  "Use the “Start telegram bot” link to connect this account."})]
        except Exception:
            pass
        return fieldsets

    readonly_fields = ("telegram_start_link",)

    @admin.display(description="Start telegram bot")
    def telegram_start_link(self, obj):
        """Kullanıcıyı bota bağlayan derin bağlantı (deep link) + token.

        Kullanıcı bu bağlantıya tıklayınca Telegram açılır ve /start <token> gönderilir;
        bot, token'dan bu hesabı bulup telegram_id'yi otomatik ekler. Telegram id'sini
        bilmeye gerek yoktur.
        """
        from django.utils.html import format_html
        if obj is None or obj.pk is None:
            return "—"
        try:
            from apps.plugins.registry import registry
            if not registry.is_enabled("telegram"):
                return "—"
            from plugins.telegram import client
            token = obj.ensure_telegram_link_token()
            bot = client.bot_username()
            if bot:
                link = f"https://t.me/{bot}?start={token}"
                return format_html(
                    '<a class="button" href="{}" target="_blank" rel="noopener">▶ Start telegram bot</a>'
                    '<div style="margin-top:6px;font-size:11px;color:#888">or send this token to the bot: '
                    '<code>{}</code></div>', link, token)
            return format_html(
                'Send this token to the bot as a message to connect: <code>{}</code>', token)
        except Exception:
            return "—"
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "given_name", "password1", "password2", "groups")}),
    )

    @admin.display(description="Roles")
    def roles_display(self, obj):
        names = list(obj.groups.values_list("name", flat=True))
        if obj.is_superuser:
            names = ["Superuser", *names]
        return ", ".join(names) or "—"

    actions = ["action_merge_users"]

    @admin.action(description="Merge selected accounts into one…")
    def action_merge_users(self, request, queryset):
        """Hesap birleştirme (OJS merge users): seçilenlerden HEDEF seçilir,
        diğerlerinin tüm kayıtları hedefe taşınır, kaynaklar pasifleştirilir."""
        from django.contrib import admin as dj_admin
        from django.contrib import messages
        from django.shortcuts import render

        from .merge import merge_users

        users = list(queryset)
        if len(users) < 2:
            self.message_user(request, "Select at least two accounts to merge.",
                              level=messages.ERROR)
            return None
        if "apply" in request.POST:
            target = queryset.filter(pk=request.POST.get("target")).first()
            if not target:
                self.message_user(request, "Choose the target account.",
                                  level=messages.ERROR)
                return None
            sources = [u for u in users if u.pk != target.pk]
            if any(u.is_superuser for u in sources):
                self.message_user(request, "Refusing to merge away a superuser account.",
                                  level=messages.ERROR)
                return None
            moved = 0
            for src in sources:
                moved += merge_users(src, target)
            self.message_user(
                request,
                f"Merged {len(sources)} account(s) into {target.email}; "
                f"{moved} record(s) reassigned. Source accounts are deactivated.")
            return None
        return render(request, "admin/merge_users.html", {
            "users": users,
            "action_checkbox_name": dj_admin.helpers.ACTION_CHECKBOX_NAME,
        })


@admin.register(JournalMembership)
class JournalMembershipAdmin(ModelAdmin):
    list_display = ("user", "journal", "role")
    list_filter = ("journal", "role")
    search_fields = ("user__email", "user__given_name", "user__family_name")
    autocomplete_fields = ("user", "journal")


@admin.register(UserInvitation)
class UserInvitationAdmin(ModelAdmin):
    list_display = ("email", "role", "journal", "invited_by", "created_at",
                    "status_display")
    list_filter = ("role", "journal")
    search_fields = ("email",)
    readonly_fields = ("token", "accepted_at", "accepted_by", "invited_by")
    actions = ["action_resend"]

    @admin.display(description="Status")
    def status_display(self, obj):
        if obj.accepted_at:
            return f"✓ accepted {obj.accepted_at:%d %b}"
        return "valid" if obj.is_valid else "expired"

    def save_model(self, request, obj, form, change):
        creating = obj.pk is None
        if creating and not obj.invited_by_id:
            obj.invited_by = request.user
        super().save_model(request, obj, form, change)
        if creating:
            from django.contrib import messages
            ok = obj.send()
            if ok:
                self.message_user(request, f"Invitation emailed to {obj.email}.")
            else:
                self.message_user(
                    request,
                    f"Invitation saved but the email could NOT be sent to {obj.email} "
                    "(is SMTP configured?). You can copy the link from the row and "
                    "send it manually, or use “Resend”.", level=messages.WARNING)

    @admin.action(description="Resend invitation email")
    def action_resend(self, request, queryset):
        from django.contrib import messages
        sent = sum(1 for inv in queryset if inv.is_valid and inv.send())
        skipped = queryset.count() - sent
        msg = f"Resent {sent} invitation(s)."
        if skipped:
            msg += f" {skipped} skipped (expired/accepted or send failed)."
        self.message_user(request, msg,
                          level=messages.WARNING if skipped else messages.INFO)


@admin.register(ApiKey)
class ApiKeyAdmin(ModelAdmin):
    change_list_template = "admin/accounts/apikey/change_list.html"
    list_display = ("user", "prefix", "name", "is_active", "created_at", "last_used_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__email", "name", "prefix")
    readonly_fields = ("prefix", "hashed_key", "created_at", "last_used_at")

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [path("generate/", self.admin_site.admin_view(self.generate_view),
                       name="accounts_apikey_generate")]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["apikey_generate_url"] = "generate/"
        return super().changelist_view(request, extra_context)

    def generate_view(self, request):
        from django.contrib import messages
        from django.shortcuts import render
        from django.urls import reverse
        from apps.accounts.models import ApiKey, User

        class GenForm(forms.Form):
            user = forms.ModelChoiceField(
                queryset=User.objects.filter(is_active=True).order_by("email"),
                initial=request.user.pk, label="Owner")
            name = forms.CharField(required=False, max_length=120,
                                   help_text="A label to recognise this key (e.g. “CI bot”).")

        raw = None
        if request.method == "POST":
            form = GenForm(request.POST)
            if form.is_valid():
                obj, raw = ApiKey.generate(form.cleaned_data["user"],
                                           name=form.cleaned_data["name"])
                messages.success(
                    request,
                    "API key created. Copy the key below now — it is shown only once "
                    "and cannot be retrieved later.")
        else:
            form = GenForm()
        return render(request, "admin/apikey_generate.html", {
            **self.admin_site.each_context(request),
            "title": "Generate API key", "form": form, "raw_key": raw,
            "changelist_url": reverse("admin:accounts_apikey_changelist"),
            "opts": self.model._meta,
        })
