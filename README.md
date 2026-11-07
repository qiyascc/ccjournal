# CC Journal

**An open-source, OJS-style academic journal management platform — built with Django, designed for self-hosting, and engineered to run on a single SQLite file with zero external services.**

CC Journal is a complete editorial and publishing system for scholarly journals: it takes a manuscript from submission, through peer review, copyediting and production, to a published, citable, DOI-registered article — with multilingual reader-facing themes, a full REST API, and OAI-PMH harvesting. It is a lean, modern alternative to Open Journal Systems (OJS), with no Celery, no Redis, and no message broker required.

---

## Table of contents

- [Project overview](#project-overview)
- [Features](#features)
- [Technology](#technology)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running in production](#running-in-production)
- [Project layout](#project-layout)
- [License](#license)

---

## Project overview

CC Journal manages the entire life-cycle of an academic journal from a single Django application. Authors submit through a guided wizard; editors run blind peer review with assignment-based access control; copyeditors and layout editors prepare the article; and the system publishes it as part of an issue, mints a DOI, deposits metadata to Crossref, and exposes it for harvesting and indexing.

The platform is intentionally **operationally simple**: it runs on SQLite in WAL mode, ships with a self-healing theme system, and requires no background workers. Everything — from the editorial workflow to the reader-facing website, the REST API, and the admin panel — lives in one deployable unit.

Design principles:

- **Thin views, fat services.** Business logic lives in service layers; views and admin actions stay small.
- **Single journal per instance**, with a clean multi-tenant-friendly data model.
- **Model → Service → View/Admin** separation throughout.
- **Typed translation tables** for every translatable model (no JSON blobs).
- **No external infrastructure** — SQLite + WAL, file-system media, synchronous email.

---

## Features

### Submission & authoring
1. **Guided submission wizard** — multi-step author submission with metadata, co-authors, files, section selection, and optional **suggested reviewers** (OJS 3.5 parity).
2. **Token-based author workspace** — authors work on their submission through a secure `/work/<token>/` URL without needing a staff account.
3. **Stage-aware file uploads** — revision, copyedit, and proofreading files are routed to the correct workflow stage automatically.
4. **Author self-service** — authors see only their own submissions and related discussions, nothing else.
5. **User dashboard** (`/dashboard/`) — logged-in users see all their submissions with stage/status, resume drafts, jump to their workspace, see review invitations and notifications in one place.
6. **Account basics done right** — email-based password reset, profile editing (`/accounts/profile/`), password change, and per-user notification preferences.

### Editorial workflow
5. **Full editorial pipeline** — Submission → Review → Copyediting → Production → Scheduled → Published, modelled on OJS.
6. **Blind peer review** — review rounds, reviewer assignments, recommendations, and editorial decisions. Reviewers work through a one-click token link: download manuscript files, submit the form, and attach an annotated file — no account required.
6b. **Automatic review reminders** — due-soon and overdue reviewers are reminded by email on a schedule, with resend protection. No cron required (see periodic tasks below).
6c. **Custom review forms** — build per-journal reviewer questionnaires (text, radio, checkboxes, dropdown; required flags) from the admin; responses are stored as snapshots so past reviews survive template edits.
6d. **Decision with email preview** — a two-step admin action lets the editor pick a decision, then edit the exact email the author will receive before anything is sent (the automatic template email is suppressed).
6e. **Stage-based file manager** — `/manage/files/<id>/` groups a submission's files into workflow-stage columns (submission → review → revisions → copyedit → proof → production-ready) with per-stage upload and "copy to next stage" (chained versions, like OJS file rounds).
7. **Editorial decisions** — send to review, request revisions, accept, send to copyediting/production, decline — each with templated author notifications.
8. **Per-stage assignments** — assign editors, copyeditors, layout editors, and proofreaders to individual submissions.
9. **Threaded discussions** — stage-scoped discussion threads between editors, authors, and assigned staff.

### Publishing & discovery
10. **Issue-gated publishing (OJS rule)** — articles cannot be published standalone; they must be assigned to an issue, and go live when the issue is published.
11. **Issue management** — volumes, numbers, years, cover images, and per-issue table of contents.
12. **DOI minting** — automatic DOI assignment on publication, with a configurable prefix.
13. **Crossref deposit** — real HTTP deposit of DOI metadata to Crossref (test & production endpoints), with safe dry-run when credentials are absent.
14. **Versioned publications** — minor/major versioning with full history of each published version.
15. **Article-level metadata** — keywords, subjects, citations, funding (Crossref/OpenAIRE-compatible), licenses, and ORCID-linked authors.

### PDF galleys & templates
16. **Automatic PDF galley generation** — render a citable, branded, DOI-stamped PDF from article metadata + abstract + full text (WeasyPrint).
17. **Visual PDF designer (no-code)** — design the PDF layout from the admin with colour pickers, font selectors, logo placement, badges, page settings, and **drag-and-drop section reordering** — no HTML/CSS required.
18. **Custom HTML/CSS mode** — advanced users can edit the raw template with `{{ variables }}` in an isolated, sandboxed template engine.
19. **Live PDF preview** — preview saved or unsaved template edits against a real article instantly, inside the admin.

### Full-text & manuscript handling
20. **Full-text article body** — store rich-text article bodies (CKEditor) that feed both the on-site reader and the generated PDF.
21. **DOCX auto-parsing** — upload a `.docx` manuscript and have it parsed into clean semantic HTML (headings, lists, emphasis, blockquotes, inline images) straight into the editor for refinement.

### Reader-facing website
22. **Multiple themes** — six built-in themes: `broadsheet` (editorial), `epictheme` (kinetic/animated), plus `default`, `sage`, `slate`, and `queenCC`.
23. **Self-healing theme system** — every theme is validated (templates compile + homepage renders) before activation; a failed theme auto-reverts.
24. **Kinetic "epic" theme** — a Lusion-inspired theme with a scroll-drawn timeline that ignites article nodes, reveal-on-scroll, ambient gradients, magnetic buttons, and **HTMX-boosted SPA-style navigation** (no full-page reloads, no loading bar). Fully respects `prefers-reduced-motion`.
25. **Full dark mode** across themes.
26. **Article pages** with abstracts, keywords, full text, galley downloads, version history, and machine-readable metadata links.
26b. **Citation export** — APA "how to cite" block plus downloadable **BibTeX** (`cite.bib`) and **RIS** (`cite.ris`) for Zotero/Mendeley/EndNote on every article.
26c. **Notify readers** — opt-in subscribers receive a localized email when a new issue is published (queued, never blocks publishing).

### Internationalisation
27. **51 content languages** — every translatable entity (journal, section, issue, publication, page) has typed translation tables.
28. **UI translation via Rosetta** — translate the interface from the browser; all 51 locales shipped with compiled message catalogs.
29. **Correct plural forms** for complex languages (Russian, Ukrainian, Arabic, Polish, Czech, etc.).
30. **Translator role** with scoped access to translation surfaces only.

### Search & metadata exchange
31. **Full-text search** — SQLite FTS5-backed search across titles, authors, and keywords.
32. **OAI-PMH provider** — harvestable metadata in Dublin Core, DataCite, and JATS formats, with tombstones for deleted records.
33. **SEO & syndication** — sitemap.xml, RSS/Atom feeds, schema.org JSON-LD on article pages.

### Roles & access control
34. **16 predefined roles** — Site Administrator, Developer, Journal Manager, Editor, Section/Guest Editor, Reviewer, Author, Copyeditor, Layout Editor, Proofreader, Translator, Designer, Journal Assistant, Subscription Manager, Reader.
34b. **User invitations (OJS 3.5-style)** — invite someone by email with a role; the link (valid 14 days) creates their account or attaches the role to their existing one.
34c. **Account merge** — merge duplicate accounts from the admin; all records move to the target, sources are deactivated.
34d. **Login throttling** — 5 failed attempts per IP/email lock sign-in for 15 minutes (no external dependency).
35. **Row-level scoping** — reviewers, copyeditors, and other production staff see only the submissions they are assigned to; editors and managers see all.
36. **Role-aware admin & sidebar** — each role sees only the modules it is permitted to use. Technical surfaces (plugins, themes, configuration, feature flags, audit log) are restricted to Site Administrator and Developer.
37. **Two-factor authentication (optional)** — TOTP/Google Authenticator 2FA via django-otp. Off by default and **toggled from the admin at runtime** (Constance → Security). When on, it applies only to Developer and superuser accounts: after username/password they must enter a 6-digit code (QR setup on first use). Five wrong codes sign the user out back to the login step. Other users are unaffected.
38. **Single source of truth** — the entire permission matrix lives in one file (`roles.py`); both the sidebar and the admin enforce it automatically.

### Platform & operations
39. **API keys** — generate scoped API keys from the admin (raw key shown once, stored hashed).
40. **REST API** — DRF-powered API with OpenAPI schema and interactive docs (drf-spectacular).
41. **Email system** — templated, multilingual transactional email with logging.
42. **Announcements, static pages, and a navigation builder** — manage site content without code.
43. **Form builder** — dynamic forms with OJS-style submission integration.
44. **Subscriptions & payments** scaffolding for paywalled or membership journals.
45. **Plugin & theme systems** — installable plugins and themes with runtime activation.
45. **WhatsApp notifications plugin** — deliver notifications over WhatsApp via a Node.js + Baileys sidecar. Enable the plugin, scan a QR code in the admin, and it runs automatically (no separate server process to manage). It reuses the existing email templates as message content and sends to each user's WhatsApp number. Disabling the plugin stops the sidecar and hides the number field (data is preserved).
46. **External-runtime plugin support** — plugins can manage external processes (e.g. Node.js services) through a built-in, gunicorn-safe sidecar process manager — no pm2 or systemd required.
47. **Audit logging, feature flags, and runtime configuration** (django-auditlog, django-waffle, django-constance).
48. **Repository snapshot & self-restore** — a built-in snapshot of code/themes that can restore the working tree, with `failnow` protecting built-in themes.
49. **Health checks** and a production-ready deployment path (gunicorn + WhiteNoise).
50. **One-command upgrade** — `python manage.py upgrade` (migrate + seeds + static); generated systemd units also run `migrate` on every start, so a code update can never leave the schema behind.
51. **Setup health card** — the admin dashboard shows exactly what is still unconfigured (sections, file types, first issue, SMTP, site URL, DOI/Crossref) with one-click links, plus a failed-background-jobs counter.
52. **Scheduled tasks without cron** — a `PeriodicRun` registry executes recurring jobs (e.g. review reminders) from the worker if present, or opportunistically from web traffic (OJS needs cron or the Acron plugin).

---

## Technology

| Layer | Choice |
|---|---|
| **Framework** | Django 6.0 |
| **Database** | SQLite (WAL mode) — no external DB server |
| **Admin** | django-unfold |
| **Frontend** | Server-rendered Django templates + Tailwind (CDN) + Alpine.js; HTMX boost on the kinetic theme |
| **Rich text** | django-ckeditor-5 |
| **PDF** | WeasyPrint |
| **DOCX import** | mammoth |
| **API** | Django REST Framework + drf-spectacular |
| **i18n** | Django i18n + django-rosetta (51 locales) |
| **Background work** | **Broker-free** DB-backed job queue + periodic tasks (no Celery/Redis; optional worker, web requests keep schedules alive otherwise) |
| **Static files** | WhiteNoise |
| **Server** | gunicorn |

Additional libraries: django-simple-history (versioning), django-auditlog (audit trail), django-waffle (feature flags), django-constance (runtime settings), django-import-export, django-countries, django-health-check, django-hijack, django-versatileimagefield, pywebpush (web push).

**Scale:** ~17,000 lines of Python across 22 apps and 59 migrations.

---

## Architecture

```
Model  →  Service  →  View / Admin
                   →  Theme template (reader site)
```

- **Models** define data and typed translation tables (e.g. `Publication` + `PublicationTranslation`).
- **Services** hold all business logic (publishing, DOI minting, Crossref deposit, PDF generation, workflow decisions). Views and admin actions call services and stay thin.
- **Themes** are filesystem template packages, resolved by a custom `ThemeTemplateLoader`. The active theme is chosen at runtime and validated before activation.
- **Templates** use explicit loaders (`APP_DIRS` disabled) so theme overrides resolve deterministically.

The single-journal model (`Journal.current()`) keeps the data model simple while remaining clean enough to support multi-tenant deployments at the infrastructure layer.

---

## Installation

### Requirements

- Python 3.12+
- System libraries for WeasyPrint (PDF rendering): `libpango-1.0-0`, `libpangocairo-1.0-0`, `libgdk-pixbuf-2.0-0`

On Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0
```

### Quick install (recommended)

CC Journal ships with a Python installer that detects your OS, installs the required
system libraries (pango/cairo/gdk-pixbuf for PDF rendering), creates the virtual
environment, installs dependencies, runs migrations and seed commands, and optionally
creates a superuser:

```bash
sudo python3 install.py
```

That's it — the installer is idempotent and can be re-run safely. For production,
use the deployment generator (below).

### Manual setup

If you prefer to do it by hand:


```bash
# 1. Clone and enter the project
cd ccjournal

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations (creates the SQLite database in WAL mode)
python manage.py migrate

# 5. Seed the 16 role groups and their permissions
python manage.py seed_roles

# 6. Create a superuser
python manage.py createsuperuser

# 7. Compile translation catalogs (optional; 51 locales ship pre-compiled)
python manage.py compilemessages

# 8. Run the development server
python manage.py runserver
```

The reader site is now at `http://localhost:8000/` and the admin at `http://localhost:8000/admin/`.

---

### WhatsApp plugin (optional)

The WhatsApp notification plugin runs a Node.js sidecar. Install its dependencies once:

```bash
cd whatsapp_service
npm install
cd ..
```

Then enable the **WhatsApp notifications** plugin in the admin (Plugins), open its
**QR / status** page, and scan the QR code with WhatsApp (Linked devices → Link a device).
The session is persistent; notifications start flowing automatically. No `pm2`/systemd is
needed — Django starts and stops the sidecar with the plugin.

---

## Configuration

Runtime settings live in **`config.ini`** (not in code), so deployments need no source changes.

Key sections:

```ini
[database]
name = db.sqlite3

[crossref]
username        =
password        =
depositor_name  =
depositor_email =
registrant      =
test_mode       = true        ; true → test.crossref.org

[push]
wp_public_key  =
wp_private_key =
```

- **DOIs**: enable per journal and set the DOI prefix in the journal settings.
- **Crossref**: without credentials, deposits run in safe **dry-run** mode (XML is generated but never sent).
- **Email**: configure SMTP in `config.ini`; the locmem backend is used in tests.

---

## Running in production

Use the deployment generator. It asks for a name (e.g. `ahuspus`) and produces
matching `ahuspus.service` (systemd + gunicorn) and `ahuspus.nginx` (reverse proxy)
files, collects static files, and can install/enable them for you:

```bash
sudo python3 deploy.py
```

You will be asked for the deployment name, system user, domain, gunicorn bind, and
worker count. The generated files land in `./deploy/`. The installer prints the exact
commands to enable the service and nginx site, plus a certbot hint for TLS.

Recommendations:

- Put TLS in front (`sudo certbot --nginx -d yourdomain`).
- Back up the SQLite file and the `media/` directory regularly.
- Keep `DEBUG = False` and set `ALLOWED_HOSTS`.

Because there is no broker or worker tier, a production deployment is just
**gunicorn (systemd) + nginx + a backup job** — all generated by `deploy.py`.

### Backups & preservation (LOCKSS-equivalent posture)

Everything lives in two places: **`db.sqlite3`** and **`media/`**. A complete,
restorable nightly backup is one cron line (uses SQLite's online-backup, safe
while the site runs):

```cron
15 3 * * * cd /srv/ccjournal && venv/bin/python -c "import sqlite3;s=sqlite3.connect('db.sqlite3');d=sqlite3.connect('backups/db-$(date +\%F).sqlite3');s.backup(d)" && rsync -a media/ backups/media/
```

For continuous off-site replication use [Litestream](https://litestream.io)
(streams the SQLite WAL to S3-compatible storage). For scholarly preservation,
the **OAI-PMH endpoint** (`/oai`, DC/DataCite/JATS) lets any archive or
aggregator harvest all published metadata, and `failnow` restores the
application code itself — from the bundled snapshot or straight from your
GitHub repository (`config.ini [repository]`).


## Project layout

```
ccjournal/
├── config/              # settings, URLs, WSGI
├── apps/
│   ├── accounts/        # users, roles, permissions, API keys, scoping
│   ├── submissions/     # submissions, files, author workspace
│   ├── review/          # peer review, decisions, discussions, assignments
│   ├── publications/    # publications, galleys, PDF generation, DOCX import
│   ├── journals/        # journal, sections, issues, categories
│   ├── metadata/        # OAI-PMH, Crossref, DOIs, tombstones
│   ├── comms/           # email templates, logs, notifications
│   ├── web/             # reader-facing views
│   ├── themes/          # theme system + loader
│   ├── search/          # FTS5 search
│   ├── api/             # REST API
│   ├── pages/ announcements/ navigation/ formbuilder/
│   ├── subscriptions/ stats/ reports/ plugins/
│   └── core/ configuration/
├── themes/              # broadsheet, epictheme, default, sage, slate
├── templates/           # base + admin overrides
├── locale/              # 51 translation catalogs
├── config.ini           # runtime configuration
└── requirements.txt
```

---

## License

Project: **CC Journal**
Developed by **Qiyas CC**
Copyright © 2026 Qiyas CC. All Rights Reserved.
