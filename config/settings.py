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
ccjournal — proje ayarları.

Yığın tercihleri: SQLite (WAL), django-unfold admin, Celery/Redis YOK,
SPA YOK (Alpine.js + server-rendered), tek-komut deploy hedefi.
"""
import configparser
import os
from pathlib import Path

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = BASE_DIR / "config.ini"
_cp = configparser.ConfigParser()
if CONFIG_FILE.exists():
    _cp.read(CONFIG_FILE, encoding="utf-8")


def cfg(section, key, default=None):
    try:
        return _cp.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default


def cfg_bool(section, key, default=False):
    return str(cfg(section, key, str(default))).strip().lower() in ("1", "true", "yes", "on")


def cfg_int(section, key, default=0):
    try:
        return int(cfg(section, key, default))
    except (TypeError, ValueError):
        return default


_INSECURE_SECRET = "dev-only-change-me"
SECRET_KEY = os.environ.get("CCJOURNAL_SECRET_KEY") or cfg("general", "secret_key", _INSECURE_SECRET)
if not SECRET_KEY or SECRET_KEY == _INSECURE_SECRET:
    _keyfile = BASE_DIR / ".secret_key"
    if _keyfile.exists():
        SECRET_KEY = _keyfile.read_text(encoding="utf-8").strip()
    else:
        from django.core.management.utils import get_random_secret_key
        SECRET_KEY = get_random_secret_key()
        try:
            _keyfile.write_text(SECRET_KEY, encoding="utf-8")
            os.chmod(_keyfile, 0o600)
        except OSError:
            pass

DEBUG = cfg_bool("general", "debug", False)
if os.environ.get("CCJOURNAL_DEBUG") is not None:
    DEBUG = os.environ["CCJOURNAL_DEBUG"].strip().lower() in ("1", "true", "yes", "on")

ALLOWED_HOSTS = [h.strip() for h in cfg("general", "allowed_hosts", "*").split(",") if h.strip()]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
_site_url = cfg("general", "site_url", "")
_origins = ([_site_url.rstrip("/")] if _site_url.startswith("http") else []) + \
    [f"https://{h}" for h in ALLOWED_HOSTS if h and h != "*"]
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_origins))
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = cfg_int("security", "hsts_seconds", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_SSL_REDIRECT = cfg_bool("security", "ssl_redirect", False)

_DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "media-src 'self' blob:; "
    "worker-src 'self' blob:; "
    "frame-src 'self' blob:; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
)
CSP_POLICY = cfg("security", "csp", _DEFAULT_CSP)

AI_API_KEY = os.environ.get("CCJOURNAL_AI_API_KEY") or cfg("ai", "api_key", "")
AI_MODEL = cfg("ai", "model", "claude-haiku-4-5-20251001")
CSP_REPORT_ONLY = cfg_bool("security", "csp_report_only", False)
REFERRER_POLICY = cfg("security", "referrer_policy", "strict-origin-when-cross-origin")
PERMISSIONS_POLICY = cfg("security", "permissions_policy",
                         "geolocation=(), microphone=(), camera=()")

INSTALLED_APPS = [
    "whitenoise.runserver_nostatic",
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.simple_history",
    "unfold.contrib.constance",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "apps.core",
    "apps.accounts",
    "apps.journals",
    "apps.submissions",
    "apps.publications",
    "apps.review",
    "apps.metadata",
    "apps.comms",
    "apps.web",
    "apps.search",
    "apps.stats",
    "apps.plugins",
    "apps.configuration",
    "apps.pages",
    "apps.navigation",
    "apps.announcements",
    "apps.subscriptions",
    "apps.reports",
    "apps.tasks",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "apps.api",
    "apps.formbuilder",
    "push_notifications",
    "rangefilter",
    "hijack",
    "hijack.contrib.admin",
    "apps.themes",
    "django_ckeditor_5",
    "rosetta",
    "import_export",
    "simple_history",
    "auditlog",
    "constance",
    "waffle",
    "django_countries",
    "versatileimagefield",
    "health_check",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "apps.adminkit",
    "django_cleanup.apps.CleanupConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.security.SecurityHeadersMiddleware",
    "apps.formbuilder.middleware.FormSubdomainMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.web.language.InterfaceLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.accounts.otp.OTPEnforcementMiddleware",
    "hijack.middleware.HijackUserMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "waffle.middleware.WaffleMiddleware",
    "apps.web.middleware.SetupMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.tasks.middleware.PeriodicPulseMiddleware",
]

ROOT_URLCONF = "config.urls"

OTP_ENABLED = cfg_bool("security", "otp_enabled", False)
OTP_TOTP_ISSUER = cfg("security", "otp_issuer", "CC Journal")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "loaders": [
                "apps.themes.loaders.ThemeTemplateLoader",
                "apps.plugins.loaders.PluginTemplateLoader",
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.comms.context_processors.notifications",
                "apps.comms.context_processors.webpush",
                "apps.journals.context_processors.branding",
                "apps.navigation.context_processors.menus",
                "apps.accounts.context_processors.orcid",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / cfg("database", "name", "db.sqlite3"),
        "OPTIONS": {
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA foreign_keys=ON;"
                "PRAGMA busy_timeout=5000;"
            ),
        },
        "TEST": {"NAME": str(BASE_DIR / "test_db.sqlite3")},
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LANGUAGE_CODE = "en"
from apps.core.locales import CONTENT_LOCALES as _CL
from apps.core.sidebar import build_navigation as _sidebar_navigation
LANGUAGES = [(code.lower(), native) for code, _en, native in _CL]
LOCALE_PATHS = [BASE_DIR / "locale"]

LANGUAGE_URL_TYPE = (cfg("language", "url_type", "query") or "query").strip().lower()
if LANGUAGE_URL_TYPE not in ("query", "slug"):
    LANGUAGE_URL_TYPE = "query"
if LANGUAGE_URL_TYPE == "slug":
    MIDDLEWARE.insert(MIDDLEWARE.index("apps.web.language.InterfaceLanguageMiddleware"),
                      "django.middleware.locale.LocaleMiddleware")
TIME_ZONE = cfg("general", "time_zone", "Asia/Baku")
USE_I18N = True
USE_TZ = True

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

if cfg("email", "host"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = cfg("email", "host")
    EMAIL_PORT = cfg_int("email", "port", 587)
    EMAIL_HOST_USER = cfg("email", "user", "")
    EMAIL_HOST_PASSWORD = cfg("email", "password", "")
    EMAIL_USE_TLS = cfg_bool("email", "use_tls", True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = cfg("email", "from", "ccjournal <noreply@example.org>")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

def _admin_brand(request=None):
    try:
        from apps.journals.models import Journal
        j = Journal.current()
        if j:
            t = j.tr()
            if t:
                return t.title
    except Exception:
        pass
    return "Journal Management"


UNFOLD = {
    "SITE_TITLE": _admin_brand,
    "SITE_HEADER": _admin_brand,
    "SITE_SYMBOL": "menu_book",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "DASHBOARD_CALLBACK": "apps.core.dashboard.dashboard_callback",
    "ENVIRONMENT": "apps.core.dashboard.environment_callback",
    "COMMAND": {"search_models": True},
    "SHOW_BACK_BUTTON": True,
    "SHOW_LANGUAGES": False,
    "SITE_DROPDOWN": [
        {"icon": "public", "title": "View site", "link": "/"},
        {"icon": "dynamic_form", "title": "Forms", "link": "/forms/"},
        {"icon": "api", "title": "API docs", "link": "/api/docs/"},
        {"icon": "summarize", "title": "Reports", "link": "/reports/"},
        {"icon": "grid_on", "title": "Role matrix", "link": "/manage/roles/"},
    ],
    "COLORS": {
        "primary": {
            "50": "245 243 255", "100": "237 233 254", "200": "221 214 254",
            "300": "196 181 253", "400": "167 139 250", "500": "139 92 246",
            "600": "124 58 237", "700": "109 40 217", "800": "91 33 182",
            "900": "76 29 149", "950": "46 16 101",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": _sidebar_navigation(),
    },
}

SITE_URL = cfg("general", "site_url", "https://example.org")
OAI = {
    "repository_name": cfg("oai", "repository_name", "ccjournal"),
    "repository_identifier": cfg("oai", "repository_id", "ccjournal.local"),
    "admin_email": cfg("oai", "admin_email", "admin@example.org"),
    "page_size": cfg_int("oai", "page_size", 50),
}
CROSSREF = {
    "depositor_name": cfg("crossref", "depositor_name", "ccjournal"),
    "depositor_email": cfg("crossref", "depositor_email", "doi@example.org"),
    "registrant": cfg("crossref", "registrant", "ccjournal"),
}

ORCID = {
    "client_id": os.environ.get("CCJOURNAL_ORCID_CLIENT_ID") or cfg("orcid", "client_id", ""),
    "client_secret": (os.environ.get("CCJOURNAL_ORCID_CLIENT_SECRET")
                      or cfg("orcid", "client_secret", "")),
    "sandbox": cfg_bool("orcid", "sandbox", False),
    # Member API: yayınları yazarın ORCID kaydına yaz (girişte /activity/update
    # kapsamı istenir; public API kimlik bilgileriyle ORCID isteği reddeder).
    "push": cfg_bool("orcid", "push", False),
}


CKEDITOR_5_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": [
            "heading", "|", "bold", "italic", "link", "bulletedList", "numberedList",
            "|", "blockQuote", "insertTable", "|", "undo", "redo",
        ],
        "table": {"contentToolbar": ["tableColumn", "tableRow", "mergeTableCells"]},
    },
}


IMPORT_EXPORT_USE_TRANSACTIONS = True
IMPORT_EXPORT_SKIP_ADMIN_LOG = False

AUDITLOG_INCLUDE_ALL_MODELS = True
AUDITLOG_EXCLUDE_TRACKING_MODELS = (
    "admin.logentry", "sessions.session", "contenttypes.contenttype",
    "auth.permission", "auditlog.logentry", "waffle.flag", "waffle.switch",
    "waffle.sample", "constance.constance",
)

SIMPLE_HISTORY_REVERT_ENABLED = True

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"
CONSTANCE_DATABASE_CACHE_BACKEND = None
from unfold.contrib.constance.settings import UNFOLD_CONSTANCE_ADDITIONAL_FIELDS  # noqa: E402
CONSTANCE_ADDITIONAL_FIELDS = dict(UNFOLD_CONSTANCE_ADDITIONAL_FIELDS)
CONSTANCE_CONFIG = {
    "MAINTENANCE_MODE": (False, "Put the public site into maintenance mode", bool),
    "MAINTENANCE_MESSAGE": ("We'll be back soon.", "Maintenance page message", str),
    "REGISTRATION_OPEN": (True, "Allow new user self-registration", bool),
    "REQUIRE_EMAIL_VERIFICATION": (False, "New accounts must click an emailed "
                                   "verification link before signing in", bool),
    "ITEMS_PER_PAGE": (20, "Articles per page in listings", int),
    "SHOW_ABSTRACT_VIEWS": (True, "Show view/download counts on article pages", bool),
    "STATS_COUNT_STAFF_VIEWS": (False, "Count staff (editor/admin) visits in usage "
                                "statistics. Off = COUNTER-style reader-only counts.", bool),
    "OTP_ENABLED": (False, "Require two-factor authentication (Google Authenticator) "
                    "for Developer and superuser accounts", bool),
    "AUTO_REMIND_INVITE_DAYS": (5, "Re-send review invitations unanswered for this "
                                "many days (0 = off)", int),
    "AUTO_NOTIFY_ALL_REVIEWS_DONE": (True, "Notify editors the moment every review "
                                     "in a round is complete", bool),
    "AUTO_STALE_REVIEW_DAYS": (30, "Alert editors when a submission has no confirmed "
                               "reviewer for this many days (0 = off)", int),
    "EMAIL_UNDO_MINUTES": (0, "Delay decision emails this many minutes so they can "
                           "be cancelled from the Jobs queue (0 = send instantly)", int),
    "BLOCK_AI_BOTS": (False, "Ask AI crawlers (GPTBot, CCBot, Google-Extended, …) "
                      "not to index the site via robots.txt", bool),
}
CONSTANCE_CONFIG_FIELDSETS = {
    "Site": ("MAINTENANCE_MODE", "MAINTENANCE_MESSAGE", "REGISTRATION_OPEN",
             "REQUIRE_EMAIL_VERIFICATION"),
    "Display": ("ITEMS_PER_PAGE", "SHOW_ABSTRACT_VIEWS", "STATS_COUNT_STAFF_VIEWS"),
    "Security": ("OTP_ENABLED",),
    "Automation": ("AUTO_REMIND_INVITE_DAYS", "AUTO_NOTIFY_ALL_REVIEWS_DONE",
                   "AUTO_STALE_REVIEW_DAYS", "EMAIL_UNDO_MINUTES"),
    "Crawlers": ("BLOCK_AI_BOTS",),
}


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.api.authentication.ApiKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "1000/min"},
}
SPECTACULAR_SETTINGS = {
    "TITLE": "ccjournal REST API",
    "DESCRIPTION": "OJS-style journal API. Authenticate with a personal API key: "
                   "`Authorization: Api-Key <key>`. Operations follow your account's role permissions.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}


HIJACK_PERMISSION_CHECK = "apps.accounts.hijack.authorize"
HIJACK_INSERT_BEFORE = None

PUSH_NOTIFICATIONS_SETTINGS = {
    "WP_PRIVATE_KEY": (os.environ.get("CCJOURNAL_VAPID_PRIVATE_KEY")
                       or cfg("push", "wp_private_key", "") or None),
    "WP_CLAIMS": {"sub": f"mailto:{cfg('push', 'wp_claims_email', 'admin@example.org')}"},
}
WEBPUSH_PUBLIC_KEY = cfg("push", "wp_public_key", "")


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ccjournal",
    }
}


TASKS_ALWAYS_EAGER = cfg_bool("tasks", "always_eager", True)


_LOG_FORMAT = (cfg("logging", "format", "text") or "text").strip().lower()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{asctime} {levelname:<7} {name}: {message}", "style": "{"},
        "json": {"()": "apps.core.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler",
                    "formatter": "json" if _LOG_FORMAT == "json" else "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "ccjournal": {"handlers": ["console"],
                      "level": cfg("logging", "level", "INFO"), "propagate": False},
    },
}

_SENTRY_DSN = os.environ.get("CCJOURNAL_SENTRY_DSN") or cfg("sentry", "dsn", "")
if _SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=("debug" if DEBUG else "production"),
            send_default_pii=False,
            traces_sample_rate=float(cfg("sentry", "traces_sample_rate", "0") or 0),
        )
    except Exception:  # noqa: BLE001 — Sentry hiçbir koşulda açılışı bloklamamalı
        import logging as _lg
        _lg.getLogger("ccjournal").warning("Sentry DSN set but sentry_sdk unavailable.")
