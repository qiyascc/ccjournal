import io
import tarfile
from pathlib import Path

import pytest

from apps.core import repo_source
from apps.core.repo_source import (
    RepoSourceError, ensure_valid_snapshot, fetch_github_tarball, parse_github,
    resolve_snapshot_root, validate_snapshot_root,
)


def _make_tree(root: Path, *, valid=True):
    (root / "apps/core").mkdir(parents=True)
    (root / "apps/journals").mkdir(parents=True)
    if valid:
        (root / "apps/submissions").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "templates").mkdir()
    (root / "themes").mkdir()
    (root / "manage.py").write_text("#!/usr/bin/env python\n")
    (root / "requirements.txt").write_text("Django\n")
    (root / "config/settings.py").write_text("ROOT_URLCONF = 'config.urls'\n")


def _tarball_bytes(rootname: str, *, valid=True) -> bytes:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / rootname
        root.mkdir()
        _make_tree(root, valid=valid)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(root, arcname=rootname)
        return buf.getvalue()


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self, n=-1):
        return self._data if n in (-1, None) else self._data[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# --- URL ayrıştırma -------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://github.com/qiyas/ccjournal",
    "https://github.com/qiyas/ccjournal.git",
    "github.com/qiyas/ccjournal/",
    "git@github.com:qiyas/ccjournal.git",
    "qiyas/ccjournal",
])
def test_parse_github_accepted_forms(url):
    assert parse_github(url) == ("qiyas", "ccjournal")


def test_parse_github_rejects_garbage():
    with pytest.raises(RepoSourceError, match="Cannot parse"):
        parse_github("https://gitlab.com/x/y")


# --- Doğrulama --------------------------------------------------------------

def test_validate_ok_and_missing(tmp_path):
    _make_tree(tmp_path, valid=True)
    assert validate_snapshot_root(tmp_path) == []
    ensure_valid_snapshot(tmp_path, source_label="X")  # raise etmemeli


def test_wrong_repo_message_is_english_and_actionable(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("some other project")
    with pytest.raises(RepoSourceError) as exc:
        ensure_valid_snapshot(tmp_path, source_label="GitHub repository foo/bar")
    msg = str(exc.value)
    assert "wrong repository" in msg
    assert "apps/core" in msg and "manage.py" in msg
    assert "repo_url" in msg


# --- GitHub indirme (mock) ----------------------------------------------------

def test_fetch_github_tarball_extracts_root(tmp_path, monkeypatch):
    data = _tarball_bytes("qiyas-ccjournal-abc123")
    monkeypatch.setattr(repo_source.urllib.request, "urlopen",
                        lambda req, timeout=0: _FakeResponse(data))
    root = fetch_github_tarball(tmp_path, repo_url="qiyas/ccjournal")
    assert root.name == "qiyas-ccjournal-abc123"
    assert validate_snapshot_root(root) == []


def test_fetch_github_http_errors(tmp_path, monkeypatch):
    import urllib.error

    def raise_404(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(repo_source.urllib.request, "urlopen", raise_404)
    with pytest.raises(RepoSourceError, match="not found"):
        fetch_github_tarball(tmp_path, repo_url="qiyas/ghost")

    def raise_401(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(repo_source.urllib.request, "urlopen", raise_401)
    with pytest.raises(RepoSourceError, match="github_token"):
        fetch_github_tarball(tmp_path, repo_url="qiyas/private", token="bad")


def test_fetch_github_rejects_non_tarball(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_source.urllib.request, "urlopen",
                        lambda req, timeout=0: _FakeResponse(b"<html>nope</html>"))
    with pytest.raises(RepoSourceError, match="not a valid tarball"):
        fetch_github_tarball(tmp_path, repo_url="qiyas/ccjournal")


# --- Kaynak çözümü ---------------------------------------------------------------

def test_resolve_uses_github_when_configured_and_validates(tmp_path, monkeypatch):
    data = _tarball_bytes("o-r-sha", valid=True)
    monkeypatch.setattr(repo_source, "github_config",
                        lambda: {"repo_url": "o/r", "token": "", "ref": ""})
    monkeypatch.setattr(repo_source.urllib.request, "urlopen",
                        lambda req, timeout=0: _FakeResponse(data))
    root, label = resolve_snapshot_root(tmp_path, base_dir=tmp_path / "nobase")
    assert "GitHub repository o/r" in label
    assert (root / "manage.py").exists()


def test_resolve_github_wrong_repo_aborts(tmp_path, monkeypatch):
    data = _tarball_bytes("o-r-sha", valid=False)   # apps/submissions eksik
    monkeypatch.setattr(repo_source, "github_config",
                        lambda: {"repo_url": "o/r", "token": "", "ref": ""})
    monkeypatch.setattr(repo_source.urllib.request, "urlopen",
                        lambda req, timeout=0: _FakeResponse(data))
    with pytest.raises(RepoSourceError, match="wrong repository"):
        resolve_snapshot_root(tmp_path, base_dir=tmp_path / "nobase")


def test_resolve_falls_back_to_local(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_source, "github_config",
                        lambda: {"repo_url": "", "token": "", "ref": ""})
    base = tmp_path / "base"
    (base / "repository").mkdir(parents=True)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        src = Path(td)
        _make_tree(src, valid=True)
        with tarfile.open(base / "repository/snapshot.tar.gz", "w:gz") as tar:
            for p in src.iterdir():
                tar.add(p, arcname=p.name)
    out = tmp_path / "out"
    out.mkdir()
    root, label = resolve_snapshot_root(out, base_dir=base)
    assert "local snapshot" in label
    assert (root / "manage.py").exists()


def test_resolve_force_local_ignores_github(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_source, "github_config",
                        lambda: {"repo_url": "o/r", "token": "", "ref": ""})

    def explode(*a, **kw):
        raise AssertionError("GitHub must not be contacted with --local")

    monkeypatch.setattr(repo_source.urllib.request, "urlopen", explode)
    base = tmp_path / "base"
    (base / "repository").mkdir(parents=True)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        src = Path(td)
        _make_tree(src, valid=True)
        with tarfile.open(base / "repository/snapshot.tar.gz", "w:gz") as tar:
            for p in src.iterdir():
                tar.add(p, arcname=p.name)
    out = tmp_path / "out"
    out.mkdir()
    root, label = resolve_snapshot_root(out, base_dir=base, force_local=True)
    assert "local snapshot" in label
