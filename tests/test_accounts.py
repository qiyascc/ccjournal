import pytest

pytestmark = pytest.mark.django_db


def test_seed_roles_creates_all_groups():
    from django.contrib.auth.models import Group
    from apps.accounts.roles import ROLE_CATALOG, seed_roles

    n = seed_roles()
    assert n == len(ROLE_CATALOG)
    for role in ROLE_CATALOG:
        assert Group.objects.filter(name=role["name"]).exists()
    editor = Group.objects.get(name="Editor")
    assert editor.permissions.filter(codename="add_publication").exists()


def test_seed_roles_is_idempotent():
    from django.contrib.auth.models import Group
    from apps.accounts.roles import seed_roles

    seed_roles()
    first = Group.objects.count()
    seed_roles()
    assert Group.objects.count() == first


def test_apikey_generate_and_resolve(django_user_model):
    from apps.accounts.models import ApiKey

    u = django_user_model.objects.create_user(
        email="k@example.org", password="pw-long-enough-123", given_name="Key")
    obj, raw = ApiKey.generate(u, name="CI bot")
    assert "." in raw
    assert obj.hashed_key != raw
    resolved = ApiKey.resolve(raw)
    assert resolved is not None and resolved.id == obj.id


def test_apikey_wrong_or_inactive_not_resolved(django_user_model):
    from apps.accounts.models import ApiKey

    u = django_user_model.objects.create_user(
        email="k2@example.org", password="pw-long-enough-123", given_name="Key")
    obj, raw = ApiKey.generate(u)
    assert ApiKey.resolve("bogus.nonsense") is None
    assert ApiKey.resolve("") is None
    obj.is_active = False
    obj.save(update_fields=["is_active"])
    assert ApiKey.resolve(raw) is None


def test_membership_bridges_group_and_staff(journal, django_user_model):
    from apps.accounts.models import JournalMembership
    from apps.accounts.roles import Role

    u = django_user_model.objects.create_user(
        email="m@example.org", password="pw-long-enough-123", given_name="Mem")
    JournalMembership.objects.create(user=u, journal=journal, role=Role.EDITOR)
    assert u.groups.filter(name="Editor").exists()
    u.refresh_from_db()
    assert u.is_staff is True
