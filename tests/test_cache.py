import pytest

pytestmark = pytest.mark.django_db


def test_version_starts_and_bumps():
    from apps.core.models import SiteState
    v0 = SiteState.version()
    assert SiteState.bump() == v0 + 1
    assert SiteState.version() == v0 + 1


def test_cached_by_version_memoizes_then_refreshes():
    from apps.core.cache import cached_by_version, invalidate

    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return calls["n"]

    assert cached_by_version("t:key", builder) == 1
    assert cached_by_version("t:key", builder) == 1
    assert calls["n"] == 1

    invalidate()
    assert cached_by_version("t:key", builder) == 2
    assert calls["n"] == 2


def test_publish_bumps_content_version(make_pub, issue_published):
    from apps.core.models import SiteState
    from apps.publications.services import PublicationService

    v0 = SiteState.version()
    PublicationService.publish(make_pub(issue=issue_published))
    assert SiteState.version() > v0


def test_menu_change_bumps_version():
    from apps.core.models import SiteState
    from apps.navigation.models import MenuArea, MenuItem, MenuKind

    v0 = SiteState.version()
    MenuItem.objects.create(area=MenuArea.PRIMARY, kind=MenuKind.URL,
                            url="/x/", is_enabled=True, seq=1)
    assert SiteState.version() > v0
