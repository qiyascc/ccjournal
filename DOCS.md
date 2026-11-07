# CC Journal — Complete Operator & Editor Handbook

> A self‑hosted academic journal platform — an OJS alternative, but easier to
> install and run. Single journal, single SQLite database, no message broker,
> no CDN. This document explains **everything**: how to install it, configure
> it, add articles, create volumes, change the ISSN, wire up email/channels,
> manage plugins, export metadata, and troubleshoot.

**Live instance:** https://journal.ubermensch.cc
**Admin:** https://journal.ubermensch.cc/admin/ (sign in with your **email**, not a username)

---

## Table of contents

1. [What CC Journal is](#1-what-cc-journal-is)
2. [Architecture at a glance](#2-architecture-at-a-glance)
3. [Installation & first run](#3-installation--first-run)
4. [Deployment, upgrade, backup](#4-deployment-upgrade-backup)
5. [`config.ini` — every section explained](#5-configini--every-section-explained)
6. [Runtime settings (Constance)](#6-runtime-settings-constance)
7. [Roles & who can do what](#7-roles--who-can-do-what)
8. [Setting up the journal (title, ISSN, DOI, locales)](#8-setting-up-the-journal)
9. [Sections](#9-sections)
10. [Volumes & Issues](#10-volumes--issues)
11. [Adding an article — the four ways](#11-adding-an-article--the-four-ways)
12. [The editorial workflow (statuses & stages)](#12-the-editorial-workflow)
13. [Peer review](#13-peer-review)
14. [Galleys & the PDF designer](#14-galleys--the-pdf-designer)
15. [Publishing an article](#15-publishing-an-article)
16. [DOI & Crossref](#16-doi--crossref)
17. [Indexing & metadata exports (OAI, DOAJ, PubMed, JATS, Scholar)](#17-indexing--metadata-exports)
18. [Discovery & SEO](#18-discovery--seo)
19. [Email & templates](#19-email--templates)
20. [Channels (email / Telegram / WhatsApp)](#20-channels)
21. [Plugins](#21-plugins)
22. [The AI editorial assistant (optional)](#22-the-ai-editorial-assistant)
23. [Newsletter & Call for Papers](#23-newsletter--call-for-papers)
24. [Reports & statistics](#24-reports--statistics)
25. [Integrity panel](#25-integrity-panel)
26. [Themes & the theme editor](#26-themes--the-theme-editor)
27. [Users, invitations, ORCID, 2FA](#27-users-invitations-orcid-2fa)
28. [Background jobs & scheduled work](#28-background-jobs--scheduled-work)
29. [Security, maintenance mode, health](#29-security-maintenance-mode-health)
30. [Management command reference](#30-management-command-reference)
31. [URL reference](#31-url-reference)
32. [Troubleshooting](#32-troubleshooting)

---

## 1. What CC Journal is

CC Journal runs **one** scholarly journal end to end: public reading site,
author submission, peer review, editorial decisions, production (PDF galleys),
publishing into issues, DOI registration, and indexing exports. It aims to be a
superset of what a small‑to‑mid journal needs from OJS, while being far simpler
to operate.

**Deliberately out of scope:** multi‑tenancy (hosting many journals from one
install) and PostgreSQL. The design is intentionally *one journal, one SQLite
file*. Do not look for a "create another journal" feature — there isn't one, by
choice.

---

## 2. Architecture at a glance

| Concern | Choice |
|---|---|
| Framework | Django 6 |
| Database | SQLite (WAL mode), single `db.sqlite3` |
| Admin | Django admin themed with **django‑unfold** |
| Background work | Built‑in DB job queue (`apps.tasks`) — **no Celery/Redis** |
| Scheduled work | Web‑request‑driven periodic pulse — **no cron required** |
| PDFs | WeasyPrint |
| Search | SQLite FTS5 full‑text index |
| Front end | Server‑rendered templates + Alpine.js + htmx, **self‑hosted (no CDN)** |
| Runtime settings | django‑constance (change from the admin, no restart) |
| Multilingual | Typed translation tables per model (title/abstract/body per locale) |

Everything the browser loads (Alpine, htmx, fonts, Sortable) is served from
`/static/` on your own domain, so a strict Content‑Security‑Policy works.

---

## 3. Installation & first run

Prerequisites: Python 3.12+, a Linux host, and the system libraries WeasyPrint
needs (Pango/Cairo/GDK‑Pixbuf).

```bash
git clone <your repo> ccjournal
cd ccjournal
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp config.ini.example config.ini      # then edit — see §5
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_roles         # role groups & permissions
./venv/bin/python manage.py seed_email_templates
./venv/bin/python manage.py createsuperuser    # email + password
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py runserver          # dev only
```

Then open `/setup/` — the **Setup health** page shows a checklist (SMTP set?
DOI configured? logo uploaded? secret key changed?) and turns red on anything
missing. Work down that list.

> **Fast demo:** `manage.py seed_demo` builds a full sample journal ("CC Test")
> with 3 issues × 6 long articles and PDFs. Add `--no-pdf` to skip PDF
> rendering (much faster). This **deletes** any prior "CC Test" data first.

---

## 4. Deployment, upgrade, backup

**Service (production).** The site runs under gunicorn behind nginx, managed by
systemd (`ccjournal.service`, bound to `0.0.0.0:9444` on the live box). The
service unit runs migrations automatically **before** each start:

```
ExecStartPre=<venv>/python manage.py migrate --noinput
```

so a deploy that ships new migrations can never boot the old schema against a
new codebase. `deploy.py` also runs `collectstatic` during a deploy.

**Upgrade in place:**

```bash
git pull
./venv/bin/python manage.py upgrade      # migrations + seeds + collectstatic (idempotent)
sudo systemctl restart ccjournal.service
```

`upgrade` is safe to run repeatedly; it just brings migrations, seed data, and
static files up to date.

**Backup.** Everything lives in two places: the SQLite file `db.sqlite3` (plus
its `-wal`/`-shm` siblings) and the `media/` directory (uploaded files, covers,
logos). Copy both. A dated DB copy before risky operations is the habit:

```bash
cp db.sqlite3 backups/db-$(date +%F).sqlite3
```

**Prove a backup restores** — don't trust an untested backup:

```bash
./venv/bin/python manage.py restore_drill              # newest backup
./venv/bin/python manage.py restore_drill path/to.sqlite3
```

It opens the backup in a temp dir, runs `migrate` + `check`, and reports
whether it came up clean.

---

## 5. `config.ini` — every section explained

`config.ini` sits in the project root and is **git‑ignored** (it holds
secrets). Values are read at process start, so **changing them needs a service
restart**. Anything you want to flip live without a restart is a Constance
setting instead (§6). Secrets can also come from environment variables:
`CCJOURNAL_SECRET_KEY`, `CCJOURNAL_AI_API_KEY`.

```ini
[general]
secret_key   = <long random string>        ; falls back to .secret_key file
debug        = false                        ; NEVER true in production
allowed_hosts = journal.ubermensch.cc       ; comma‑separated
site_url     = https://journal.ubermensch.cc/
time_zone    = Asia/Baku

[repository]
repo_url     = https://github.com/you/ccjournal
github_token = <PAT>                         ; used by the failnow/restore tooling
ref          =

[database]
engine = sqlite
name   = db.sqlite3

[email]                                      ; SMTP — see §19
host     =                                   ; EMPTY = emails only print to the log
port     = 587
user     =
password =
use_tls  = true
from     = CC Journal <noreply@example.org>

[oai]                                        ; OAI‑PMH endpoint identity (§17)
repository_name = ccjournal
repository_id   = ccjournal.local
admin_email     = admin@example.org
page_size       = 50

[crossref]                                   ; DOI deposit identity (§16)
depositor_name  = ccjournal
depositor_email = doi@example.org
registrant      = ccjournal

[forms]
subdomain = form                             ; optional form builder subdomain

[language]
url_type = slug                              ; "slug" → /en/path  ·  "query" → ?lang=en

[push]                                        ; Web Push (VAPID) keys
wp_public_key  = <vapid public>
wp_private_key = <vapid private>
wp_claims_email = admin@example.org

[channels]
hook_secret = <shared secret>                ; verifies inbound reply webhooks (§20)

[ai]                                          ; optional AI assistant (§22)
api_key =                                     ; EMPTY = AI features invisible
model   = claude-haiku-4-5-20251001

[security]
otp_enabled     = false                       ; 2FA for superusers/developers
otp_issuer      = CC Journal
csp             = <override the default policy, optional>
csp_report_only = false
hsts_seconds    = 31536000
ssl_redirect    = false
referrer_policy = strict-origin-when-cross-origin

[orcid]                                       ; ORCID sign‑in / review push (§27)
client_id     =
client_secret =
push          = false
sandbox       = false

[sentry]
dsn = 
traces_sample_rate = 0

[logging]
level  = INFO
format = text                                 ; "json" for structured logs

[tasks]
always_eager = true                           ; true = run jobs inline (no worker)
```

> **Security note on `script-src`.** The site's CSP allows
> `'unsafe-eval'` in `script-src` — Alpine.js compiles its directives with
> `new Function()` and needs it. Script *sources* are still restricted to
> `'self'` (no third‑party JS). If you override `csp`, keep `'unsafe-eval'`.

---

## 6. Runtime settings (Constance)

Change these live from **Admin → Constance → Config** — no restart, effect is
immediate.

| Key | Default | What it does |
|---|---|---|
| `MAINTENANCE_MODE` | false | Puts the public site into a maintenance page |
| `MAINTENANCE_MESSAGE` | "We'll be back soon." | Text on that page |
| `REGISTRATION_OPEN` | true | Allow new users to self‑register |
| `REQUIRE_EMAIL_VERIFICATION` | false | New accounts must click an emailed link before signing in |
| `ITEMS_PER_PAGE` | 20 | Articles per page in listings |
| `SHOW_ABSTRACT_VIEWS` | true | Show view/download counts on article pages |
| `STATS_COUNT_STAFF_VIEWS` | false | Count editor/admin visits in stats (off = COUNTER‑style reader‑only) |
| `OTP_ENABLED` | false | Require 2FA (Google Authenticator) for Developer + superusers |
| `AUTO_REMIND_INVITE_DAYS` | 5 | Re‑send unanswered review invitations after N days (0 = off) |
| `AUTO_NOTIFY_ALL_REVIEWS_DONE` | true | Ping editors when every review in a round is in |
| `AUTO_STALE_REVIEW_DAYS` | 30 | Alert editors when a submission has no confirmed reviewer for N days (0 = off) |
| `EMAIL_UNDO_MINUTES` | 0 | Delay decision emails N minutes so they can be cancelled from the Jobs queue |
| `BLOCK_AI_BOTS` | false | Ask AI crawlers (GPTBot, CCBot, Google‑Extended…) not to index, via robots.txt |

---

## 7. Roles & who can do what

Run `manage.py seed_roles` once (installation does this). It creates these
groups with the right permissions:

`Site Administrator`, `Journal Manager`, `Editor`, `Section Editor`,
`Guest Editor`, `Reviewer`, `Author`, `Reader`, `Copyeditor`, `Layout Editor`,
`Proofreader`, `Designer`, `Translator`, `Journal Assistant`,
`Subscription Manager`, `Developer`.

Assign a user to roles in **Admin → Users → (user) → Groups**, or grant
journal‑scoped membership under **Journal Memberships**. "Editorial access"
(seeing `/manage/...` tools) means superuser **or** a member of an editor‑class
group.

---

## 8. Setting up the journal

There is exactly one journal record. **Admin → Journals → Journal.**

Key fields:

- **Title / description** — per locale (translation rows).
- **`primary_locale` / `supported_locales`** — the languages the journal
  publishes in; drives the public language switcher and translation slots.
- **`issn_print` / `issn_online`** — see below.
- **`publisher`, `contact_email`.**
- **`doi_prefix`, `enable_doi`** — see §16.
- **`enable_oai`** — expose the OAI‑PMH endpoint.
- **`default_review_mode`** — anonymity default for new review rounds.
- **`theme`** — active theme key (or use the Themes admin, §26).
- **`logo`** — appears in the header and on PDF galleys.

### Changing the ISSN

**Admin → Journals → Journal →** the `issn_print` and `issn_online` fields →
Save. That's the only place. The value flows automatically into:

- the article page's `citation_issn` meta tag (Google Scholar, §17),
- the JSON‑LD `isPartOf.issn`,
- Crossref/DOAJ exports.

> **Important:** if you do **not** have a real ISSN yet, leave both fields
> **empty**. An invalid or placeholder ISSN (e.g. a made‑up `2792‑1234`) is
> *worse* than none — Google Scholar may mis‑group or reject the journal. The
> field is validated for format but you are responsible for it being a real,
> assigned number. Fill it in only once your ISSN centre has issued one.

---

## 9. Sections

Sections are the article categories inside the journal (e.g. "Research
Articles", "Reviews", "Editorials"). **Admin → Journals → Sections → Add.**

Useful fields: `abstracts_required`, `is_indexed` (whether it appears in
indexing exports), `is_editor_restricted` (only editors can submit to it),
`review_mode` (override the journal default), `word_count_limit`.

Every published article belongs to one section.

---

## 10. Volumes & Issues

CC Journal models a "volume" as a field on an **Issue**. To create what a reader
sees as "Volume 3, Issue 1 (2026)":

**Admin → Journals → Issues → Add.**

- **`volume`** — the integer volume number (e.g. 3).
- **`number`** — the issue label within the volume (e.g. "1", or "1‑2").
- **`year`** — publication year.
- **`is_published`** — untick while you assemble it; tick to make it public.
- **`is_current`** — marks the issue shown as "current" on the home page (only
  one should be current).
- **`access` / `open_access_date`** — open vs. subscription, and an optional
  moving‑wall date.
- **`cover_image`** — optional cover.
- **`galley_file`** — optional single‑file PDF of the whole issue.

Typical flow: create the issue **unpublished** → assign accepted articles to it
(on each Publication, set the `issue` and `pages`) → when complete, run the
**issue closing checklist** (Admin → Issues → select → *Issue checklist* action)
which flags missing galleys, DOIs, ORCIDs, or TOC gaps → then tick
`is_published` (and `is_current`). Publishing an issue can email readers and
newsletter subscribers a table of contents (§19).

---

## 11. Adding an article — the four ways

### (a) Public submission wizard — the author route
`/submit/` walks an author through: start → **files** → **metadata** →
**authors** → **confirm** → done. Authors can work with a token‑based
workspace even without a full account. On confirm they set data‑availability
and AI‑use statements and pick a CC licence. This creates a `Submission` in
**Queued** status that enters the editorial workflow.

### (b) Quick submit (format‑free) — `/submit/quick/`
"Science first, we'll handle the format." The author uploads a single DOCX; the
system extracts the title and body automatically, so there's no multi‑step form
to fight. Great for first‑time or busy authors.

### (c) Editorial direct entry — the admin
Editors can create records directly: **Admin → Submissions → Submissions → Add**
(then add its Publication, translations, authors, keywords), or work from the
public wizard on the author's behalf. Use this for invited content or
back‑filling legacy material.

### (d) Import existing content
- **From OJS:** `manage.py import_ojs export.xml` — reads an OJS *native XML*
  export (issues + articles) and creates them here. Namespace‑agnostic parser.
- **From another CC Journal:** `manage.py import_ccj package.zip` — imports a
  "cascade package" (see below). Round‑trips a whole submission (metadata,
  files, author‑visible reviews) in seconds.

> **Cascade package.** When a submission is **declined**, its author can
> download a single `.zip` from their workspace
> (`/work/<token>/package.zip`) containing full metadata, files, and the
> reviewer comments meant for them. Any CC Journal install can turn that zip
> straight into a new submission with `import_ccj` — no reformatting.

---

## 12. The editorial workflow

A submission has a **stage** and a **status**.

**Stages:** `Submission (1)` → `Review (3)` → `Editing/Copyedit (4)` →
`Production (5)`.

**Statuses:** `Incomplete/draft (0)`, `Queued (1)`, `Published (3)`,
`Declined (4)`, `Scheduled (5)`.

Editorial tools live under `/manage/…` (editors/superusers only):

- **Files** — `/manage/files/<id>/` — every file across rounds, one‑click send
  to review or promote to galley.
- **Reviews** — `/manage/reviews/<id>/` — all review assignments side by side,
  plus deterministic reviewer suggestions (and, if enabled, an AI shortlist).
- **Integrity** — `/manage/integrity/<id>/` — see §25.
- **Dossier PDF** — `/manage/dossier/<id>.pdf` — the full file/decision/review
  timeline as one PDF.
- **Editorial board** — `/manage/board/` — a live kanban of submissions.
- **Roles** — `/manage/roles/`.

**Editorial decisions** (accept / minor‑or‑major revisions / decline) are
recorded from the submission's admin/review page. Each decision can send a
templated email to the author, with a **preview** and an optional **undo
window** (`EMAIL_UNDO_MINUTES`). Authors can file **one appeal** on a declined
submission from their workspace, which notifies the editors.

---

## 13. Peer review

- **Reviewer pool** — users with a **Reviewer Profile** (Admin → Review →
  Reviewer Profiles): interests, affiliation, availability, and self‑service
  fields (see below).
- **Assigning** — from the review round's admin page (autocomplete by
  name/email). The **Reviews** manage page suggests reviewers deterministically
  (keyword overlap + history − current load, with conflict‑of‑interest flags).
- **Invitations & reminders** — invitations can be auto‑re‑sent after
  `AUTO_REMIND_INVITE_DAYS`. Editors are pinged when a round is complete
  (`AUTO_NOTIFY_ALL_REVIEWS_DONE`) and warned about stale submissions
  (`AUTO_STALE_REVIEW_DAYS`).
- **Reviewer experience** — a reviewer gets a **tokenised link** (`/review/<token>/`),
  no account required: read the files, submit the form, upload attachments,
  and even **decline‑and‑suggest‑a‑colleague**.
- **One‑touch accept** — over Telegram/WhatsApp a reviewer can reply `1`
  (accept) or `2` (decline) to an invitation (§20).
- **Recognition** — a reviewer can download a **PDF certificate**
  (`/review/<token>/certificate.pdf`), receive an annual summary
  (`manage.py reviewer_year_summary`), and opt into the public **`/reviewers/`**
  thank‑you page.
- **Self‑service** — on their profile page a reviewer sets **vacation mode**
  (`unavailable_until`), a **yearly cap** (`max_per_year`), and whether to be
  listed publicly. These feed the suggestion engine automatically.

---

## 14. Galleys & the PDF designer

A **galley** is a published rendition of the article — usually a PDF, sometimes
HTML/XML. **Admin → Publications → (publication) → Galleys**, or promote a file
from the Files manager. Set `is_approved` to make it public. Approved galleys
appear on the article page and are what `citation_pdf_url` points Google Scholar
to (§17).

**PDF designer.** `/admin/publications/pdftemplate/add/` (and the change page)
is a **visual** designer — no code:

- **Colors** (accent, secondary, body, muted, panel background).
- **Typography & logo** (heading/body font, logo position & size).
- **Badge & rule** (e.g. "RESEARCH ARTICLE" badge, header underline) — toggle
  switches.
- **Page** (size A4/Letter/A5, margins, footer text, page numbers).
- **Sections** — drag to reorder, toggle to show/hide (brand, badge, title,
  subtitle, authors, affiliations, meta, abstract, keywords, body).

Switch **Mode** to *Custom HTML/CSS* for full control; variables include
`{{ title }}`, `{{ authors }}`, `{{ abstract }}`, `{{ body }}`, `{{ logo_url }}`,
`{{ doi }}`, `{{ keywords }}`, `{{ issue_line }}`. Save once to unlock the **live
PDF preview** (it renders a real article from the journal).

---

## 15. Publishing an article

1. Article accepted and copyedited; an **approved PDF galley** exists.
2. On its **Publication**: set the **`issue`**, **`pages`** (e.g. `12-28`),
   licence, copyright, and any data/AI statements.
3. Publish it (editorial workflow / Publication admin). This sets status
   **Published**, stamps `date_published`, adds it to the issue's table of
   contents, and rebuilds the search index entry.
4. If DOI is enabled, mint/deposit the DOI (§16). For legacy articles there's a
   **retroactive DOI** admin action.

Versions are supported (`version_major`/`version_minor`); the newest published
version is the "current" one shown to readers.

---

## 16. DOI & Crossref

- Enable on the journal: `enable_doi = true`, set `doi_prefix` (e.g. `10.5555`).
- Identity for deposits comes from `config.ini [crossref]`
  (`depositor_name/email`, `registrant`).
- DOIs are minted per publication (and optionally per galley). A **retroactive
  DOI** action exists for back‑catalogue.
- **Crossref deposit XML:** `/export/crossref` — includes **Crossmark** policy
  metadata when configured.
- Cited‑by counts are fetched periodically from **OpenCitations** and shown on
  the article page.

---

## 17. Indexing & metadata exports

| What | Where |
|---|---|
| **OAI‑PMH** | `/oai` (identity from `config.ini [oai]`; enable per journal) |
| **Crossref deposit** | `/export/crossref` |
| **DOAJ article XML** | `/export/doaj` |
| **PubMed XML** | `/export/pubmed` |
| **JATS (per article)** | `/article/<id>/jats.xml` |
| **Sitemap** | `/sitemap.xml` |
| **RSS/Atom** | `/feed/`, `/feed/atom/`, `/feed/section/<id>/`, `/feed/keyword/<term>/` |

### Google Scholar (Highwire meta tags)

Every article page emits the full set of `citation_*` tags Scholar relies on,
built from your existing data:

`citation_title`, `citation_author` (repeated), `citation_journal_title`,
`citation_issn`, `citation_publication_date`, `citation_volume`,
`citation_issue`, `citation_firstpage`/`citation_lastpage` (parsed from
`pages`), `citation_doi`, `citation_language`, `citation_abstract`, and — the
critical one — **`citation_pdf_url`** pointing at the approved PDF galley.

These are centralised in `templates/partials/citation_meta.html` and shared by
all themes. **Note:** Scholar indexing is not instant even when the tags are
perfect — its crawler re‑visits on its own schedule, which can take **weeks**.
Make sure the PDF galley is public and the ISSN is real (or empty).

---

## 18. Discovery & SEO

- **Related articles** under "How to cite" (full‑text word overlap, no AI).
- **Search facets** by year and section on `/search/`.
- **Keyword pages** `/keyword/<term>/` and **author pages** `/author/<id>/`.
- **Most‑cited** `/most-cited/`.
- **OpenGraph cards** — a 1200×630 PNG per article at `/article/<id>/card.png`,
  referenced via `og:image`, plus `hreflang` alternates per translation.
- **Listen to article** — browser speech synthesis, zero CDN.
- **robots.txt / AI bots** — `/robots.txt` allows normal crawlers; flip
  `BLOCK_AI_BOTS` (Constance) to ask GPTBot/CCBot/Google‑Extended not to index.

---

## 19. Email & templates

**SMTP.** Set `config.ini [email]`. **If `host` is empty, no email is actually
sent** — messages are written to the log instead (safe for dev; the Setup
health page flags this red). This is the single most common "why didn't my
email arrive" cause.

**Templates.** **Admin → Comms → Email Templates**, seeded per locale by
`manage.py seed_email_templates`. Keys include: `decision_accept`,
`decision_decline`, `decision_revisions`, `review_request`, `review_reminder`,
`user_invitation`, `email_verification`, `issue_published`,
`publication_published`. Each template supports variables rendered from context.

- **Send me a test** — an action on each template renders it with sample data
  and sends it to you.
- **Undo window** — decision/custom emails can be delayed `EMAIL_UNDO_MINUTES`
  and cancelled from **Admin → Tasks → Jobs** before they fire.
- **Issue TOC** — publishing an issue emails a table of contents; the
  `issue_published` body includes a `{{ toc }}` block.

---

## 20. Channels

Notifications go out over pluggable **channels**. **Email** is built in.
**Telegram** and **WhatsApp** are plugins (§21):

- **Telegram** — bot notifications + author self‑service; a reviewer can reply
  `1`/`2` to accept/decline an invitation directly in chat.
- **WhatsApp** — delivery via a Node.js + Baileys **sidecar** process; inbound
  replies post back to `/hooks/channel-reply/`.

Inbound reply webhooks are authenticated with a shared secret:
`config.ini [channels] hook_secret` (sent as the `X-CCJ-Hook-Secret` header).
Keep it long and private.

---

## 21. Plugins

CC Journal has a real plugin system (parallel to OJS plugin categories). Plugins
live in `plugins/<name>/`, expose `plugin = <Plugin subclass>()`, subscribe to
hooks in `register()`, and can ship their own `templates/`. They're
**toggled in Admin → Plugins → Plugins** (enable/disable takes effect without a
code change).

**Discover / sync / install:**

```bash
./venv/bin/python manage.py plugins            # list discovered plugins, sync to DB
./venv/bin/python manage.py install_plugin path/to/plugin.zip
```

**Bundled plugins:**

| Plugin | Category | What it does |
|---|---|---|
| `article_share` | block | Share/cite box on the article page |
| `doi_year` | pubId | DOI suffix strategy that includes the year |
| `email_signature` | generic | Appends a signature to outgoing email |
| `oai_simple` | oaiMetadata | Extra/simple OAI metadata format |
| `telegram` | generic | Telegram notifications + reviewer self‑service |
| `whatsapp` | generic | WhatsApp delivery via Baileys sidecar |
| `ai_assistant` | generic | Optional LLM editorial helpers (§22) |

**Hook types:** `do_action(name, **kw)` (fire‑and‑forget notifications) and
`apply_filters(name, value, **kw)` (transform a value through a chain).
Disabled plugins' callbacks are skipped at runtime. Example hook points:
`templates.article_extra`, `manage.integrity_extra`, `manage.reviews_extra`,
`submission.submitted`, `publication.published`, `email.body`, `doi.suffix`.

---

## 22. The AI editorial assistant (optional)

`plugins/ai_assistant` — a fully optional, plugin‑gated LLM helper. **If
`config.ini [ai] api_key` is empty, it leaves no trace in the UI.** To turn it
on: put an Anthropic API key in `[ai] api_key` (or `CCJOURNAL_AI_API_KEY`), then
enable "AI editorial assistant" in **Admin → Plugins**, and restart.

Everything it produces is a **suggestion for a human** — nothing is applied
automatically. Four helpers:

1. **Desk‑check briefing** — auto on new submissions (can be disabled) and
   on‑demand on the integrity panel: scope fit, missing items, language
   quality, signals to check. Never recommends accept/reject.
2. **Metadata extraction** — pulls title/abstract/keywords from the manuscript;
   the editor ticks what to apply on the integrity panel.
3. **Review synthesis** — on `/manage/reviews/<id>/`: agreements, disagreements,
   merged revision requests, neutral options for the editor.
4. **Reviewer shortlist** — an LLM second opinion over the deterministic
   suggestions, with COI/overload flags.

**How it's built:** calls the Anthropic Messages API via stdlib `urllib` (no new
dependency), runs through the job queue (requests never block), and stores its
reports as `PluginSetting` rows (no migration). Default model is Haiku
(cheap — roughly a cent per article); change it in the plugin settings
(`model`). Toggle auto desk‑check with the plugin's `auto_desk_check` setting.

> Privacy: with the assistant on, pre‑publication manuscript text is sent to the
> API. State this in your editorial/ethics policy.

---

## 23. Newsletter & Call for Papers

- **Newsletter** — accountless, **double opt‑in**. Readers subscribe at
  `/newsletter/`, confirm via a signed link, and every mail carries a signed
  unsubscribe link. Publishing an issue also mails confirmed subscribers the
  TOC.
- **Call for Papers** — **Admin → Journals → Calls For Papers**. Active calls
  show a homepage banner and a public `/calls/` page.
- **Highlights** — **Admin → Journals → Highlights** — featured items on the
  home page.
- **Announcements** — **Admin → Announcements**; public at `/announcements/`
  with its own feed.

---

## 24. Reports & statistics

**`/reports/`** (editorial access) links to CSVs and dashboards:

| Report | URL |
|---|---|
| Submissions | `/reports/submissions.csv` |
| Reviews | `/reports/reviews.csv` |
| Users | `/reports/users.csv` |
| Subscriptions | `/reports/subscriptions.csv` |
| Usage (page) | `/reports/usage/` |
| Usage (CSV) | `/reports/usage.csv` |
| COUNTER | `/reports/counter.csv` |
| Editorial timings | `/reports/editorial.csv` |

**Counting** follows a COUNTER‑style model: a 30‑second double‑click filter, and
staff visits excluded by default (`STATS_COUNT_STAFF_VIEWS = false`). Article
pages show a 12‑month readership sparkline. Daily metrics live in **Admin →
Stats → Metrics (Daily)**.

---

## 25. Integrity panel

`/manage/integrity/<id>/` — a small journal's answer to iThenticate, built from
free signals: Crossref reference‑DOI validation, retracted‑source detection,
archive similarity, disposable‑email domains, and self‑citation. It runs
automatically at submission and can be re‑run (including live Crossref) from the
page. If the AI assistant is on, its desk‑check and metadata panels appear here
too.

---

## 26. Themes & the theme editor

Bundled themes: `broadsheet` (the live default), `default`, `epictheme`,
`queenCC`, `sage`, `slate`. Activate one in **Admin → Themes** (or the journal's
`theme` field).

**Mini theme editor** — `/manage/theme/` — override CSS custom properties
(colors, etc.) without touching files. Great for quick brand tweaks.

---

## 27. Users, invitations, ORCID, 2FA

- **Sign‑in identity is the email address** (there are no usernames).
- **Registration** — `/accounts/register/`, gated by `REGISTRATION_OPEN`;
  optionally require email verification (`REQUIRE_EMAIL_VERIFICATION`).
- **Invitations** — **Admin → Accounts → User Invitations**; the invitee sets a
  password via `/accounts/invite/<token>/`.
- **Password reset** — `/accounts/password/reset/` (needs working SMTP).
- **ORCID sign‑in** — configure `config.ini [orcid]` (`client_id/secret`,
  `sandbox`); users sign in via `/accounts/orcid/login/`. With `push = true`,
  completed reviews can be pushed to a reviewer's ORCID record.
- **Two‑factor (TOTP)** — flip `OTP_ENABLED` (Constance) or `[security]
  otp_enabled`. When on, **Developers and superusers** are required to set up
  Google Authenticator on first admin login (`/admin/otp/`); other users are
  unaffected.

---

## 28. Background jobs & scheduled work

- **Job queue** — `apps.tasks`. With `[tasks] always_eager = true` (default),
  jobs run **inline** — no worker needed, fine for small volume. Jobs are
  visible in **Admin → Tasks → Jobs**.
- **Worker (optional)** — for higher volume set `always_eager = false` and run
  `manage.py run_worker` (add it to systemd).
- **Periodic work** — a lightweight middleware pulse runs due periodic tasks off
  normal web requests, so **no cron is required**. It also drains due queued
  jobs. (In tests this pulse is disabled via a module flag.)

---

## 29. Security, maintenance mode, health

- **Security headers** — CSP (self‑hosted assets, `'unsafe-eval'` for Alpine),
  HSTS, `X‑Frame‑Options: DENY`, nosniff, referrer policy, permissions policy.
  Tune via `config.ini [security]`.
- **Maintenance mode** — flip `MAINTENANCE_MODE` (Constance) to show a
  maintenance page with `MAINTENANCE_MESSAGE`.
- **Health check** — `/health/`.
- **Setup health** — `/setup/` — the operator checklist.
- **Emergency restore** — `manage.py failnow` restores the default project
  structure from a bundled snapshot (uses `[repository]` for source); pair with
  `manage.py buildrepo` to rebuild that snapshot.

---

## 30. Management command reference

| Command | App | Purpose |
|---|---|---|
| `upgrade` | core | In‑place upgrade: migrations + seeds + static (idempotent) |
| `seed_roles` | accounts | Create/refresh role groups & permissions |
| `seed_email_templates` | comms | Seed default email templates per locale |
| `seed_menus` | navigation | Seed default navigation menus |
| `seed_demo` | core | Build the "CC Test" demo journal (`--no-pdf` to skip PDFs) |
| `rebuild_search` | search | Rebuild the FTS index from published articles |
| `import_ojs` | core | Import an OJS native XML export |
| `import_ccj` | core | Import a CC Journal cascade package (`.zip`) |
| `reviewer_year_summary` | review | Email reviewers their yearly summary |
| `restore_drill` | core | Verify a SQLite backup restores cleanly |
| `plugins` | plugins | List/sync plugins |
| `install_plugin` | plugins | Install a plugin from a `.zip` |
| `run_worker` | tasks | Run the DB job‑queue worker (broker‑free) |
| `buildrepo` | core | Rebuild the snapshot used by `failnow` |
| `failnow` | core | EMERGENCY: restore default project structure |

---

## 31. URL reference

**Public**
```
/                         home
/issues/                  issue archive
/issue/<id>/              issue TOC        /issue/<id>/galley/  whole‑issue PDF
/article/<id>/            article
/article/<id>/cite.bib    BibTeX           /article/<id>/cite.ris  RIS
/article/<id>/jats.xml    JATS             /article/<id>/card.png  OG card
/article/<id>/galley/<g>/ PDF (download)   /article/<id>/view/<g>/ inline view
/section/<id>/            section          /keyword/<term>/  keyword page
/author/<id>/             author page      /most-cited/      most cited
/search/                  search           /reviewers/       reviewer thanks
/calls/                   calls for papers /accessibility/   a11y statement
/newsletter/              subscribe        /announcements/   announcements
/sitemap.xml  /robots.txt  /feed/  /feed/atom/  /feed/section/<id>/  /feed/keyword/<term>/
```

**Author / reviewer (tokenised, no account needed)**
```
/submit/  /submit/quick/            submission wizard / quick submit
/work/<token>/                      author workspace
/work/<token>/upload/               add files
/work/<token>/package.zip           cascade package (declined only)
/work/<token>/credit/<atoken>/      co‑author CRediT approval
/work/<token>/appeal/               file an appeal
/review/<token>/                    reviewer landing
/review/<token>/form/               review form
/review/<token>/file/<id>/          download a review file
/review/<token>/certificate.pdf     reviewer certificate
```

**Editorial (`/manage/…`, editorial access)**
```
/manage/board/                      editorial kanban
/manage/roles/                      role management
/manage/files/<id>/                 files manager
/manage/reviews/<id>/               reviews side‑by‑side + suggestions
/manage/integrity/<id>/             integrity panel
/manage/dossier/<id>.pdf            dossier PDF
/manage/theme/                      mini theme editor
/manage/calendar/<token>/editorial.ics   editorial ICS calendar
/manage/ai/run/<kind>/<id>/  /manage/ai/apply-metadata/<id>/   AI assistant (if enabled)
```

**Admin & data**
```
/admin/                             Django/Unfold admin
/reports/                           reports & CSVs
/oai  /export/crossref  /export/doaj  /export/pubmed   indexing exports
/api/v1/  /api/docs/  /api/schema/   REST API
/health/  /setup/                    health & setup checklist
```

---

## 32. Troubleshooting

- **Email doesn't arrive.** `config.ini [email] host` is empty → mail only goes
  to the log. Set real SMTP and restart. Check `/setup/`.
- **Article not in Google Scholar.** Confirm the article page shows
  `citation_pdf_url` and the PDF galley is public (open it in a private window).
  Ensure the ISSN is real or empty. Then wait — Scholar re‑crawls on its own
  schedule (weeks). See §17.
- **Menus/switches feel "stuck" or dead after clicking a link.** That's an
  Alpine.js init issue; the CSP must allow `'unsafe-eval'` in `script-src`
  (§5) and the site must not double‑initialise Alpine after htmx swaps. Both
  are fixed in current builds — hard‑refresh once.
- **PDF designer toggles do nothing.** Fixed — switches are now real
  `<label>` toggles. Hard‑refresh the admin page.
- **Migrations "unapplied" after deploy.** The systemd unit runs
  `migrate` on start (`ExecStartPre`); if you run gunicorn another way, run
  `manage.py migrate` yourself or use `manage.py upgrade`.
- **Admin login bounces to `/admin/otp/`.** 2FA is on (`OTP_ENABLED`). Set up
  Google Authenticator once, or turn `OTP_ENABLED` off in Constance.
- **A background job seems stuck.** With `always_eager = true` jobs run inline;
  if you switched to worker mode, make sure `run_worker` is running. Inspect
  **Admin → Tasks → Jobs**.
- **Search results look stale.** `manage.py rebuild_search`.

---

*CC Journal — developed by **Qiyas CC**. © 2026 Qiyas CC. All rights reserved.*
