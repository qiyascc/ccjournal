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

"""Self-restore snapshot source resolution.

Two sources for the factory snapshot used by `manage.py failnow`:

  * **GitHub** — when `config.ini` has `[repository] repo_url` (and optionally
    `github_token` for private repos, `ref` for a branch/tag), the snapshot is
    downloaded as a tarball from the GitHub API. The extracted tree is then
    **validated**: it must actually look like a CC Journal codebase; if it does
    not, restore aborts with a clear "wrong repository" error instead of
    clobbering the install with foreign code.
  * **Local** — otherwise the bundled `repository/snapshot.tar.gz`
    (built with `manage.py buildrepo`) is used, exactly as before.

All user-facing messages here are English by design.
"""
from __future__ import annotations

import io
import re
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

MAX_TARBALL_BYTES = 200 * 1024 * 1024

REQUIRED_MARKERS = [
    "manage.py",
    "requirements.txt",
    "config/settings.py",
    "apps/core",
    "apps/journals",
    "apps/submissions",
    "templates",
    "themes",
]


class RepoSourceError(Exception):
    """Raised with an English, user-actionable message."""


def github_config() -> dict:
    """Read [repository] settings; empty repo_url means 'not configured'."""
    try:
        from apps.configuration.services import Config
        get = Config.get
    except Exception:
        def get(section, key, default=""):
            return default
    return {
        "repo_url": (get("repository", "repo_url", "") or "").strip(),
        "token": (get("repository", "github_token", "") or "").strip(),
        "ref": (get("repository", "ref", "") or "").strip(),
    }


def parse_github(repo_url: str) -> tuple[str, str]:
    """Accepts https/ssh/short forms and returns (owner, repo)."""
    url = repo_url.strip()
    m = (re.match(r"^(?:https?://)?(?:www\.)?github\.com[/:]([^/]+)/([^/#?]+?)(?:\.git)?/?$", url)
         or re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
         or re.match(r"^([\w.-]+)/([\w.-]+?)(?:\.git)?$", url))
    if not m:
        raise RepoSourceError(
            f"Cannot parse GitHub repository URL: “{repo_url}”. "
            "Use https://github.com/<owner>/<repo> or <owner>/<repo>.")
    return m.group(1), m.group(2)


def fetch_github_tarball(dest_dir: Path, *, repo_url: str, token: str = "",
                         ref: str = "") -> Path:
    """Download + extract the repo tarball into dest_dir; return the tree root."""
    owner, repo = parse_github(repo_url)
    api = f"https://api.github.com/repos/{owner}/{repo}/tarball"
    if ref:
        api += f"/{ref}"
    req = urllib.request.Request(api, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ccjournal-failnow",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read(MAX_TARBALL_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RepoSourceError(
                f"GitHub rejected the request ({exc.code}) for {owner}/{repo}. "
                "Check [repository] github_token — it must be valid and allowed "
                "to read this repository.") from exc
        if exc.code == 404:
            raise RepoSourceError(
                f"GitHub repository {owner}/{repo} was not found (404). "
                "Check [repository] repo_url; for a private repository also set "
                "github_token.") from exc
        raise RepoSourceError(
            f"GitHub download failed for {owner}/{repo}: HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise RepoSourceError(
            f"Could not reach GitHub: {exc.reason}. Check network access, or "
            "remove [repository] repo_url to restore from the local snapshot.") from exc
    if len(data) > MAX_TARBALL_BYTES:
        raise RepoSourceError(
            f"The tarball of {owner}/{repo} exceeds the "
            f"{MAX_TARBALL_BYTES // (1024 * 1024)} MB safety limit — this does "
            "not look like a CC Journal code repository.")

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            tar.extractall(dest_dir, filter="data")
    except (tarfile.TarError, EOFError) as exc:
        raise RepoSourceError(
            f"Downloaded data from {owner}/{repo} is not a valid tarball: {exc}") from exc

    roots = [p for p in Path(dest_dir).iterdir() if p.is_dir()]
    if len(roots) == 1:
        return roots[0]
    return Path(dest_dir)


def validate_snapshot_root(root: Path) -> list[str]:
    """Return the list of CC Journal markers missing under `root`."""
    return [m for m in REQUIRED_MARKERS if not (root / m).exists()]


def ensure_valid_snapshot(root: Path, *, source_label: str) -> None:
    missing = validate_snapshot_root(root)
    if missing:
        raise RepoSourceError(
            f"{source_label} does not look like a CC Journal codebase — wrong "
            f"repository? Missing: {', '.join(missing)}. Point [repository] "
            "repo_url at your CC Journal repository, or remove the setting to "
            "restore from the bundled local snapshot.")


def resolve_snapshot_root(tmp_dir: Path, *, base_dir: Path,
                          force_local: bool = False) -> tuple[Path, str]:
    """Extract the configured snapshot into tmp_dir and return (root, label).

    GitHub when configured (unless force_local), else the local tarball.
    Both sources are validated before anything is restored.
    """
    cfgv = github_config()
    if cfgv["repo_url"] and not force_local:
        label = f"GitHub repository {cfgv['repo_url']}"
        root = fetch_github_tarball(tmp_dir, repo_url=cfgv["repo_url"],
                                    token=cfgv["token"], ref=cfgv["ref"])
        ensure_valid_snapshot(root, source_label=label)
        return root, label

    snap = base_dir / "repository" / "snapshot.tar.gz"
    if not snap.exists():
        raise RepoSourceError(
            "repository/snapshot.tar.gz not found. Run `python manage.py "
            "buildrepo` on a healthy install, or configure [repository] "
            "repo_url to restore from GitHub.")
    with tarfile.open(snap, "r:gz") as tar:
        tar.extractall(tmp_dir, filter="data")
    root = Path(tmp_dir)
    ensure_valid_snapshot(root, source_label="The local snapshot")
    return root, "local snapshot (repository/snapshot.tar.gz)"
