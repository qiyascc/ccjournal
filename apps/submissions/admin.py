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
from apps.accounts.scoping import ScopedAdminMixin
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from apps.publications.models import (
    Author, Citation, Funding, Galley, Keyword, Publication, PublicationStatus,
    PublicationTranslation, Subject,
)
from django.contrib.contenttypes.admin import GenericTabularInline

from apps.comms.models import EmailLog
from .models import Genre, Submission, SubmissionFile


class EmailLogInline(GenericTabularInline):
    model = EmailLog
    extra = 0
    can_delete = False
    fields = ("created_at", "template_key", "to_emails", "subject", "status")
    readonly_fields = fields
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False


class SubmissionFileInline(TabularInline):
    model = SubmissionFile
    extra = 0
    fields = ("original_filename", "file_stage", "genre", "uploader", "seq")
    tab = True


@admin.register(Submission)
class SubmissionAdmin(ScopedAdminMixin, ModelAdmin):
    submission_path = ""
    inlines = [SubmissionFileInline, EmailLogInline]
    list_display = ("id", "__str__", "journal", "stage", "status", "date_submitted",
                    "files_link")
    list_filter = ("journal", "stage", "status")
    search_fields = ("submitter__email", "publications__translations__title")
    date_hierarchy = "created_at"
    autocomplete_fields = ("submitter", "current_publication")
    filter_horizontal = ("categories",)
    exclude = ("suggested_reviewers", "integrity_report")
    readonly_fields = ("suggested_reviewers_display", "integrity_checked_at")

    @admin.display(description="Tools")
    def files_link(self, obj):
        from django.utils.html import format_html
        badge = ""
        overall = (obj.integrity_report or {}).get("overall")
        if overall == "alert":
            badge = " ⛔"
        elif overall == "warn":
            badge = " ⚠"
        return format_html(
            '<a href="/manage/files/{0}/">📂 Files</a> · '
            '<a href="/manage/reviews/{0}/">⚖ Reviews</a> · '
            '<a href="/manage/integrity/{0}/">🛡{1}</a> · '
            '<a href="/manage/dossier/{0}.pdf">📑</a>', obj.pk, badge)
    actions = ["action_decide_with_email",
               "action_send_to_review", "action_request_revisions", "action_accept",
               "action_send_to_copyedit", "action_send_to_production", "action_decline"]

    @admin.action(description="Record decision + edit notification email…")
    def action_decide_with_email(self, request, queryset):
        """OJS akışı: karar verirken yazara gidecek e-postayı önizle/düzenle.

        Adım 1: karar + not → Adım 2: şablondan dolan e-postayı düzenle →
        kararı uygula + (istenirse) düzenlenmiş e-postayı gönder. Otomatik
        şablon e-postası bastırılır (notify_author=False).
        """
        from django.contrib import admin as dj_admin
        from django.contrib import messages
        from django.shortcuts import render
        from apps.comms.services import MailService, NotificationService
        from apps.comms.utils import absolute_url
        from apps.review.models import EditorialDecision
        from apps.review.services import WorkflowService

        if queryset.count() != 1:
            self.message_user(request, "Select exactly one submission for this action.",
                              level=messages.ERROR)
            return None
        sub = queryset.first()
        author = sub.submitter
        author_email = (author.email if author else "") or ""
        journal = sub.journal
        pub = sub.current_publication
        title = (pub.tr_value("title") if pub else "") or f"Submission #{sub.pk}"

        D = EditorialDecision.Decision
        key_map = {
            D.ACCEPT: ("decision_accept", {}),
            D.DECLINE: ("decision_decline", {}),
            D.INITIAL_DECLINE: ("decision_decline", {}),
            D.PENDING_REVISIONS: ("decision_revisions", {}),
            D.RESUBMIT: ("decision_revisions", {}),
            D.SEND_TO_COPYEDIT: ("author_action", {"title": "Your article is in copyediting"}),
            D.SEND_TO_PRODUCTION: ("author_action", {"title": "Proof ready for your review"}),
            D.SEND_TO_REVIEW: (None, {}),
        }

        base_ctx = {
            "publications": queryset, "sub": sub, "stitle": title,
            "author_email": author_email,
            "decisions": D.choices,
            "action_checkbox_name": dj_admin.helpers.ACTION_CHECKBOX_NAME,
        }

        if "apply" in request.POST:
            decision = int(request.POST.get("decision"))
            note = request.POST.get("note", "")
            subject = request.POST.get("subject", "").strip()
            body = request.POST.get("body", "")
            send = request.POST.get("send_email") == "on"
            WorkflowService.record_decision(sub, request.user, decision,
                                            note=note, notify_author=False)
            sent_msg = ""
            if send and author_email and subject:
                results = NotificationService.notify_raw(
                    journal=journal, to=[author_email], subject=subject,
                    body=body, key="decision_custom", related=sub)
                ok = any(ok for ok, _ in results.values())
                sent_msg = " Email sent." if ok else " Email could NOT be sent (check logs)."
            self.message_user(
                request, f"Decision recorded: {D(decision).label}.{sent_msg}")
            return None

        if "preview" in request.POST:
            decision = int(request.POST.get("decision"))
            note = request.POST.get("note", "")
            key, extra = key_map.get(decision, (None, {}))
            subject, body = "", ""
            if key:
                supported = journal.supported_locales or [journal.primary_locale]
                pref = getattr(author, "preferred_locale", None) if author else None
                locale = pref if pref in supported else journal.primary_locale
                ctx = {"title": extra.get("title", title), "journal": str(journal),
                       "note": note, "decision": D(decision).label,
                       "work_url": absolute_url(f"/work/{sub.author_token}/"),
                       "kind": ""}
                rendered = MailService.render(key, journal=journal, locale=locale,
                                              context=ctx)
                if rendered:
                    subject, body = rendered
            if request.POST.get("include_reviews") == "on":
                body = (body + self._reviewer_comments_block(sub)).strip()
            return render(request, "admin/decide_email.html", {
                **base_ctx, "step": 2, "decision": decision,
                "decision_label": D(decision).label, "note": note,
                "subject": subject, "body": body, "has_template": bool(key),
            })

        return render(request, "admin/decide_email.html", {**base_ctx, "step": 1})

    @staticmethod
    def _reviewer_comments_block(sub) -> str:
        """Tamamlanmış değerlendirmelerin yazara açık yorumları (anonim numaralı)."""
        from apps.review.models import ReviewAssignment
        done = (ReviewAssignment.objects
                .filter(review_round__submission=sub, date_completed__isnull=False)
                .order_by("date_completed"))
        parts = []
        for i, a in enumerate(done, start=1):
            if not a.comments_for_author.strip():
                continue
            rec = a.get_recommendation_display() if a.recommendation else ""
            head = f"Reviewer {i}" + (f" — {rec}" if rec else "")
            parts.append(f"------ {head} ------\n{a.comments_for_author.strip()}")
        return ("\n\n" + "\n\n".join(parts)) if parts else ""

    @admin.display(description="Suggested reviewers (by author)")
    def suggested_reviewers_display(self, obj):
        from django.utils.html import format_html, format_html_join
        rows = obj.suggested_reviewers or []
        if not rows:
            return "—"
        return format_html(
            "<ul style='margin:0;padding-left:1em'>{}</ul>",
            format_html_join(
                "", "<li><b>{}</b> &lt;{}&gt;{}</li>",
                ((r.get("name", ""), r.get("email", ""),
                  f" — {r['reason']}" if r.get("reason") else "") for r in rows)))

    def _decide(self, request, queryset, decision, label):
        from apps.review.services import WorkflowService
        for sub in queryset:
            WorkflowService.record_decision(sub, request.user, decision)
        self.message_user(request, f"Decision applied to {queryset.count()} submission(s): {label}.")

    @admin.action(description="Send to review")
    def action_send_to_review(self, request, queryset):
        from apps.review.models import EditorialDecision
        self._decide(request, queryset, EditorialDecision.Decision.SEND_TO_REVIEW, "Send to review")

    @admin.action(description="Request revisions (notifies author)")
    def action_request_revisions(self, request, queryset):
        from apps.review.models import EditorialDecision
        self._decide(request, queryset, EditorialDecision.Decision.PENDING_REVISIONS,
                     "Request revisions")

    @admin.action(description="Accept")
    def action_accept(self, request, queryset):
        from apps.review.models import EditorialDecision
        self._decide(request, queryset, EditorialDecision.Decision.ACCEPT, "Accept")

    @admin.action(description="Send to copyediting (notifies author)")
    def action_send_to_copyedit(self, request, queryset):
        from apps.review.models import EditorialDecision
        self._decide(request, queryset, EditorialDecision.Decision.SEND_TO_COPYEDIT,
                     "Send to copyediting")

    @admin.action(description="Send to production")
    def action_send_to_production(self, request, queryset):
        from apps.review.models import EditorialDecision
        self._decide(request, queryset, EditorialDecision.Decision.SEND_TO_PRODUCTION, "Send to production")

    @admin.action(description="Decline")
    def action_decline(self, request, queryset):
        from apps.review.models import EditorialDecision
        self._decide(request, queryset, EditorialDecision.Decision.DECLINE, "Decline")


@admin.register(Genre)
class GenreAdmin(ModelAdmin):
    list_display = ("name", "journal", "key", "is_supplementary", "is_dependent")
    list_filter = ("journal",)


from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget


class PublicationTranslationForm(forms.ModelForm):
    class Meta:
        model = PublicationTranslation
        fields = "__all__"
        widgets = {"body": CKEditor5Widget(config_name="default")}


class PublicationTranslationInline(StackedInline):
    model = PublicationTranslation
    form = PublicationTranslationForm
    extra = 1
    tab = True


class AuthorInline(StackedInline):
    model = Author
    extra = 1
    tab = True
    fields = (
        ("given_name", "family_name"), ("email", "orcid"),
        ("affiliation", "affiliation_ror", "country"), "credit_roles", "seq",
    )


class KeywordInline(TabularInline):
    model = Keyword
    extra = 1
    tab = True


class SubjectInline(TabularInline):
    model = Subject
    extra = 0
    tab = True


class CitationInline(TabularInline):
    model = Citation
    extra = 0
    tab = True


class FundingInline(TabularInline):
    model = Funding
    extra = 0
    tab = True


class GalleyInline(TabularInline):
    model = Galley
    extra = 0
    tab = True


@admin.register(Publication)
class PublicationAdmin(ScopedAdminMixin, ModelAdmin):
    submission_path = "submission"
    inlines = [
        PublicationTranslationInline, AuthorInline, KeywordInline,
        SubjectInline, CitationInline, FundingInline, GalleyInline,
    ]
    list_display = ("__str__", "version_label", "status", "section", "issue", "date_published")
    list_filter = ("status", "version_stage", "section", "issue")
    search_fields = ("translations__title",)
    autocomplete_fields = ("submission", "section", "issue")
    readonly_fields = ("version_major", "version_minor")
    actions = ["action_minor_version", "action_major_version", "action_assign_issue",
               "action_import_body", "action_generate_pdf", "action_generate_jats",
               "action_publish", "action_unpublish", "action_mint_retroactive",
               "action_crossref_deposit", "action_crossref_deposit_bg"]

    class Media:
        js = ("js/metadata_autocomplete.js",)

    @admin.action(description="Mint DOIs retroactively (published, missing DOI)")
    def action_mint_retroactive(self, request, queryset):
        """Eski sayılar için toplu DOI: yayımlanmış ama DOI'siz seçimlere bas."""
        from django.contrib import messages
        from apps.publications.models import PublicationStatus
        from apps.publications.services import DoiService
        minted = skipped = 0
        for pub in queryset:
            if pub.status != PublicationStatus.PUBLISHED or pub.doi_id:
                skipped += 1
                continue
            doi = DoiService.mint_for_publication(pub)
            minted += int(bool(doi))
            if doi is None:
                skipped += 1
        msg = f"Minted {minted} DOI(s)."
        if skipped:
            msg += (f" {skipped} skipped (unpublished, already had a DOI, or "
                    "DOI minting is disabled on the journal).")
        msg += " Next: run “Deposit DOIs to Crossref”."
        self.message_user(request,
                          msg, level=messages.WARNING if skipped else messages.INFO)

    @admin.action(description="Generate JATS XML galley (metadata record)")
    def action_generate_jats(self, request, queryset):
        from django.contrib import messages
        from apps.publications.jats import generate_jats_galley
        n = 0
        for pub in queryset:
            try:
                generate_jats_galley(pub)
                n += 1
            except Exception as e:  # noqa: BLE001
                self.message_user(request, f"#{pub.submission_id}: JATS failed — {e}",
                                  level=messages.ERROR)
        if n:
            self.message_user(request, f"Generated/updated {n} JATS XML galley(s).")

    @admin.action(description="Parse manuscript (.docx) into full-text body")
    def action_import_body(self, request, queryset):
        from django.contrib import messages
        from apps.publications.docx_import import import_body_from_manuscript
        ok = 0
        for pub in queryset:
            t, warnings = import_body_from_manuscript(pub, overwrite=True)
            if t is None:
                self.message_user(request, f"#{pub.submission_id}: {warnings[0]}",
                                  level=messages.WARNING)
            else:
                ok += 1
                if warnings:
                    self.message_user(
                        request,
                        f"#{pub.submission_id}: imported with {len(warnings)} note(s) "
                        f"(e.g. {warnings[0]}).", level=messages.INFO)
        if ok:
            self.message_user(
                request, f"Parsed {ok} manuscript(s) into the full-text body. "
                "Open the article and refine in the editor; then Generate PDF galley.")

    @admin.action(description="Generate PDF galley (from metadata + abstract)")
    def action_generate_pdf(self, request, queryset):
        from django.contrib import messages
        from apps.publications.pdf import generate_pdf_galley
        n = 0
        for pub in queryset:
            try:
                generate_pdf_galley(pub)
                n += 1
            except Exception as e:  # noqa: BLE001
                self.message_user(request, f"#{pub.submission_id}: PDF failed — {e}",
                                  level=messages.ERROR)
        if n:
            self.message_user(request, f"Generated/updated {n} PDF galley(s). "
                              "They are approved and ready; review before publishing if needed.")

    @admin.action(description="Deposit DOIs to Crossref")
    def action_crossref_deposit(self, request, queryset):
        from django.contrib import messages
        from apps.metadata.crossref import deposit_publications
        pubs = [p for p in queryset if p.doi_id]
        if not pubs:
            self.message_user(request, "None of the selected items have a DOI. "
                              "Publish them first (DOIs are minted on publish).",
                              level=messages.WARNING)
            return
        result = deposit_publications(pubs)
        if result.get("dry_run"):
            self.message_user(
                request,
                "Crossref credentials are not configured (config.ini [crossref]). "
                f"Deposit XML was generated for {len(result['dois'])} DOI(s) but not sent. "
                "Use the “Export › Crossref” endpoint to download the XML, or add "
                "credentials to deposit directly.", level=messages.WARNING)
        elif result.get("ok"):
            self.message_user(request,
                              f"Submitted {result['submitted']} DOI(s) to Crossref "
                              f"({'test' if __import__('django.conf', fromlist=['settings']).settings.CROSSREF.get('test_mode') else 'production'}). "
                              "Registration completes asynchronously.")
        else:
            self.message_user(request, f"Crossref deposit failed: {result.get('detail')}",
                              level=messages.ERROR)

    @admin.action(description="Deposit DOIs to Crossref (background, retried)")
    def action_crossref_deposit_bg(self, request, queryset):
        """Deposit'i iş kuyruğuna atar — isteği bloklamaz, hata olursa yeniden denenir.
        İşlenmesi için bir worker gerekir: `python manage.py run_worker`."""
        from django.contrib import messages
        from apps.metadata.tasks import deposit_publications_job
        from apps.tasks.queue import enqueue
        ids = [p.id for p in queryset if p.doi_id]
        if not ids:
            self.message_user(request, "None of the selected items have a DOI. "
                              "Publish them first (DOIs are minted on publish).",
                              level=messages.WARNING)
            return
        enqueue(deposit_publications_job, ids)
        self.message_user(request, f"Queued Crossref deposit for {len(ids)} DOI(s). "
                          "A worker will process it (run_worker); retries on failure.")

    @admin.action(description="Assign selected to an issue…")
    def action_assign_issue(self, request, queryset):
        """OJS akışı: önce makaleyi bir sayıya bağla, sonra sayıyı yayımla."""
        from django.contrib import admin as dj_admin
        from django.contrib import messages
        from django.shortcuts import render
        from apps.publications.models import PublicationStatus
        from apps.publications.services import PublicationService
        from apps.submissions.models import SubmissionStatus
        from apps.journals.models import Issue
        if "apply" in request.POST:
            issue = Issue.objects.filter(pk=request.POST.get("issue")).first()
            if not issue:
                self.message_user(request, "Choose an issue.", level=messages.ERROR)
                return
            n = 0
            for pub in queryset:
                pub.issue = issue
                pub.save(update_fields=["issue"])
                if issue.is_published:
                    try:
                        PublicationService.publish(pub)
                    except Exception:
                        pass
                else:
                    pub.status = PublicationStatus.SCHEDULED
                    pub.save(update_fields=["status"])
                    sub = pub.submission
                    sub.status = SubmissionStatus.SCHEDULED
                    sub.save(update_fields=["status", "date_status_modified"])
                n += 1
            self.message_user(
                request,
                f"{n} article(s) assigned to “{issue}”. "
                + ("The issue is already published, so they are live now."
                   if issue.is_published else
                   "They are now SCHEDULED — they go live when you publish the issue."))
            return
        issues = Issue.objects.order_by("-year", "-volume", "-number")[:100]
        return render(request, "admin/assign_issue.html", {
            "publications": queryset, "issues": issues,
            "action_checkbox_name": dj_admin.helpers.ACTION_CHECKBOX_NAME,
        })

    @admin.action(description="Create new version (minor)")
    def action_minor_version(self, request, queryset):
        from apps.publications.services import PublicationService
        for pub in queryset:
            new = PublicationService.create_version(pub, minor=True)
            self.message_user(request, f"Created {new.version_label} for #{pub.submission_id}.")

    @admin.action(description="Create new version (major)")
    def action_major_version(self, request, queryset):
        from apps.publications.services import PublicationService
        for pub in queryset:
            new = PublicationService.create_version(pub, minor=False)
            self.message_user(request, f"Created {new.version_label} for #{pub.submission_id}.")

    @admin.action(description="Publish selected (requires an assigned issue)")
    def action_publish(self, request, queryset):
        from django.contrib import messages
        from django.core.exceptions import ValidationError
        from apps.publications.services import PublicationService
        for pub in queryset:
            try:
                PublicationService.publish(pub)
                if pub.status == PublicationStatus.SCHEDULED:
                    self.message_user(
                        request,
                        f"{pub}: scheduled in “{pub.issue}”. It will go live when that "
                        f"issue is published.")
                else:
                    self.message_user(request, f"Published: {pub}.")
            except ValidationError as e:
                self.message_user(request, f"#{pub.submission_id}: {'; '.join(e.messages)}",
                                  level=messages.ERROR)

    @admin.action(description="Unpublish selected")
    def action_unpublish(self, request, queryset):
        from apps.publications.services import PublicationService
        for pub in queryset:
            PublicationService.unpublish(pub)
        self.message_user(request, "Unpublished (tombstones created for published items).")
