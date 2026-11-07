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
Kullanıcı + Rol modeli.

OJS yaklaşımı: kullanıcı hesapları GLOBAL'dir; roller her dergi (context) için ayrı
atanır (user_groups + user_user_groups). Aynı kişi A dergisinde Editör, B dergisinde
Yazar olabilir. Bunu net bir `JournalMembership` ara tablosuyla modelliyoruz.
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.db import models
from django_countries.fields import CountryField

from apps.core.models import TimeStampedModel, validate_orcid, validate_ror
from .roles import (  # noqa: F401
    EDITORIAL_ROLE_NAMES, ROLE_BY_KEY, STAFF_ROLE_NAMES, Role,
)


EDITORIAL_ROLES = {
    Role.SITE_ADMIN, Role.DEVELOPER, Role.JOURNAL_MANAGER,
    Role.EDITOR, Role.SECTION_EDITOR, Role.GUEST_EDITOR,
}


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("E-posta zorunlu.")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField(unique=True)
    given_name = models.CharField(max_length=150)
    family_name = models.CharField(max_length=150, blank=True)

    orcid = models.CharField(
        max_length=19, blank=True, validators=[validate_orcid], db_index=True
    )
    orcid_access_token = models.CharField(
        max_length=64, blank=True, editable=False,
        help_text="OAuth token from ORCID sign-in; required for ORCID push")
    orcid_token_scope = models.CharField(max_length=128, blank=True, editable=False)
    affiliation = models.CharField(max_length=255, blank=True)
    affiliation_ror = models.CharField(max_length=64, blank=True, validators=[validate_ror])
    country = CountryField(blank=True)
    biography = models.TextField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, db_index=True)
    telegram_id = models.CharField(max_length=32, blank=True, db_index=True)
    telegram_username = models.CharField(max_length=64, blank=True)
    telegram_link_token = models.CharField(max_length=48, blank=True, db_index=True)
    preferred_locale = models.CharField(max_length=14, default="az")
    notify_new_issue = models.BooleanField(
        default=True, help_text="Email me when a new issue is published")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    journals = models.ManyToManyField(
        "journals.Journal", through="accounts.JournalMembership", related_name="members"
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["given_name"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.full_name

    def ensure_telegram_link_token(self) -> str:
        """Kullanıcıya kalıcı bir Telegram bağlama anahtarı verir (yoksa üretir)."""
        if not self.telegram_link_token:
            import secrets
            self.telegram_link_token = secrets.token_urlsafe(18)
            self.save(update_fields=["telegram_link_token"])
        return self.telegram_link_token

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}".strip()

    def roles_in(self, journal) -> set[str]:
        return set(
            self.memberships.filter(journal=journal).values_list("role", flat=True)
        )

    @property
    def role_names(self) -> set[str]:
        """Atanmış grup (rol) adları."""
        return set(self.groups.values_list("name", flat=True))

    def has_role(self, name: str) -> bool:
        return self.is_superuser or name in self.role_names

    def has_editorial_access(self, journal=None) -> bool:
        return self.is_superuser or bool(self.role_names & EDITORIAL_ROLE_NAMES)

    def sync_staff(self) -> None:
        """Grup üyeliğine göre admin (is_staff) erişimini ayarlar."""
        should = self.is_superuser or bool(self.role_names & STAFF_ROLE_NAMES)
        if self.is_staff != should:
            self.is_staff = should
            self.save(update_fields=["is_staff"])


class JournalMembership(TimeStampedModel):
    """Kullanıcı <-> Dergi rol bağlaması (OJS: user_user_groups)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    journal = models.ForeignKey(
        "journals.Journal", on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)

    reviewer_interests = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = ("user", "journal", "role")
        verbose_name = "Journal Membership"
        verbose_name_plural = "Journal Memberships"

    def __str__(self) -> str:
        return f"{self.user} · {self.journal} · {self.get_role_display()}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.contrib.auth.models import Group
        name = ROLE_BY_KEY.get(self.role, {}).get("name")
        if name:
            group, _ = Group.objects.get_or_create(name=name)
            self.user.groups.add(group)


def _invite_token():
    import secrets
    return secrets.token_urlsafe(32)


class UserInvitation(TimeStampedModel):
    """Rol davetiyesi (OJS 3.5 user invitation karşılığı).

    Editör e-posta + rol seçerek davet oluşturur; davetli linkten hesabını kurar
    (veya mevcut hesabına giriş yapar) ve rol JournalMembership olarak eklenir.
    """
    email = models.EmailField()
    journal = models.ForeignKey("journals.Journal", on_delete=models.CASCADE,
                                related_name="invitations")
    role = models.CharField(max_length=20, choices=Role.choices)
    token = models.CharField(max_length=64, unique=True, db_index=True,
                             default=_invite_token, editable=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    message = models.TextField(blank=True, help_text="Davet e-postasına eklenecek not")
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")

    VALID_DAYS = 14

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User invitation"

    def __str__(self) -> str:
        return f"{self.email} → {self.get_role_display()}"

    @property
    def is_valid(self) -> bool:
        from datetime import timedelta

        from django.utils import timezone
        if self.accepted_at:
            return False
        return timezone.now() - self.created_at <= timedelta(days=self.VALID_DAYS)

    def send(self) -> bool:
        """Davet e-postasını gönderir (user_invitation şablonu)."""
        from apps.comms.services import MailService
        from apps.comms.utils import absolute_url
        return MailService.send(
            "user_invitation", journal=self.journal,
            locale=self.journal.primary_locale, to=[self.email], related=self,
            context={"journal": str(self.journal),
                     "role": self.get_role_display(),
                     "message": self.message,
                     "invite_url": absolute_url(f"/accounts/invite/{self.token}/")})


class ApiKey(models.Model):
    """OJS-vari kişisel API anahtarı. Anahtar yalnızca oluşturulurken bir kez gösterilir;
    veritabanında SHA-256 hash'i saklanır. İstekler sahibin rol yetkileriyle çalışır."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="api_keys")
    name = models.CharField(max_length=120, blank=True, help_text="Etiket (ör. 'CI botu')")
    prefix = models.CharField(max_length=12, db_index=True, editable=False)
    hashed_key = models.CharField(max_length=64, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "API key"

    def __str__(self) -> str:
        return f"{self.user} · {self.prefix}… ({self.name or 'key'})"

    @staticmethod
    def _hash(raw: str) -> str:
        import hashlib
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def generate(cls, user, name: str = ""):
        """Yeni anahtar üretir; (ApiKey, ham_anahtar) döner. Ham anahtar bir daha görünmez."""
        import secrets
        prefix = secrets.token_hex(4)
        secret = secrets.token_urlsafe(32)
        raw = f"{prefix}.{secret}"
        obj = cls.objects.create(user=user, name=name, prefix=prefix,
                                 hashed_key=cls._hash(raw))
        return obj, raw

    @classmethod
    def resolve(cls, raw: str):
        """Ham anahtardan aktif ApiKey'i bulur (yoksa None)."""
        if not raw or "." not in raw:
            return None
        prefix = raw.split(".", 1)[0]
        h = cls._hash(raw)
        return cls.objects.filter(prefix=prefix, hashed_key=h, is_active=True).first()
