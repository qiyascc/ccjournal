from datetime import timedelta

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_enqueue_creates_queued_job():
    from apps.tasks.models import Job
    from apps.tasks.queue import enqueue

    j = enqueue("builtins.abs", -3)
    assert j.status == Job.Status.QUEUED
    assert j.func == "builtins.abs" and j.args == [-3]
    assert j.attempts == 0


def test_run_due_runs_and_marks_done():
    from apps.tasks.models import Job
    from apps.tasks.queue import enqueue, run_due

    enqueue("builtins.abs", -9)
    assert run_due() == 1
    j = Job.objects.get()
    assert j.status == Job.Status.DONE
    assert j.result == 9
    assert j.attempts == 1
    assert j.finished_at is not None


def test_retry_with_backoff_then_dead_letter():
    from apps.tasks.models import Job
    from apps.tasks.queue import enqueue, run_job

    j = enqueue("builtins.int", "not-a-number", max_attempts=2)

    run_job(j)
    j.refresh_from_db()
    assert j.status == Job.Status.QUEUED
    assert j.attempts == 1
    assert j.run_after > timezone.now()
    assert j.last_error

    j.run_after = timezone.now()
    j.save(update_fields=["run_after"])
    run_job(j)
    j.refresh_from_db()
    assert j.status == Job.Status.FAILED
    assert j.attempts == 2


def test_run_due_respects_run_after():
    from apps.tasks.queue import enqueue, run_due

    enqueue("builtins.abs", -1, run_after=timezone.now() + timedelta(hours=1))
    assert run_due() == 0


def test_non_jsonable_result_stored_as_str():
    from apps.tasks.models import Job
    from apps.tasks.queue import enqueue, run_due

    enqueue("builtins.object")
    run_due()
    j = Job.objects.get()
    assert j.status == Job.Status.DONE
    assert isinstance(j.result, str) and "object" in j.result


def test_enqueue_or_run_eager_runs_inline(settings):
    from apps.tasks.models import Job
    from apps.tasks.queue import enqueue_or_run

    settings.TASKS_ALWAYS_EAGER = True
    result = enqueue_or_run("builtins.abs", -5)
    assert result == 5
    assert Job.objects.count() == 0


def test_enqueue_or_run_non_eager_enqueues(settings):
    from apps.tasks.models import Job
    from apps.tasks.queue import enqueue_or_run

    settings.TASKS_ALWAYS_EAGER = False
    obj = enqueue_or_run("builtins.abs", -5)
    assert isinstance(obj, Job)
    assert obj.status == Job.Status.QUEUED
    assert Job.objects.count() == 1


def test_publish_indexes_for_search(make_pub, issue_published):
    """publish() -> enqueue_or_run(eager) -> reindex -> FTS: makale aranabilir."""
    from apps.publications.services import PublicationService
    from apps.search.services import SearchIndex

    pub = make_pub(issue=issue_published, title="Quantum Entanglement Study")
    PublicationService.publish(pub)
    assert pub.submission_id in SearchIndex.search("quantum")


def test_crossref_deposit_job_dry_run(make_pub, issue_published, journal):
    """Kimlik bilgisi yokken deposit job'u güvenle dry-run döner (istisna fırlatmaz)."""
    from apps.publications.services import PublicationService
    journal.enable_doi = True
    journal.doi_prefix = "10.1234"
    journal.save(update_fields=["enable_doi", "doi_prefix"])
    pub = make_pub(issue=issue_published)
    PublicationService.publish(pub)

    from apps.metadata.tasks import deposit_publications_job
    res = deposit_publications_job([pub.id])
    assert res["dry_run"] is True
    assert res["ok"] is False
