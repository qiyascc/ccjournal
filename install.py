#!/usr/bin/env python3
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

"""CC Journal — installer.

Usage:
    sudo python3 install.py

What it does:
  1. Detects the operating system / distro.
  2. Installs the required system packages (WeasyPrint needs pango/cairo/gdk-pixbuf;
     optionally Node.js for the WhatsApp plugin).
  3. Creates a Python virtual environment (./venv).
  4. Installs Python dependencies from requirements.txt.
  5. Creates config.ini from the example if missing.
  6. Runs database migrations and the standard seed commands.
  7. Asks whether to create a superuser (y/N).

Re-runnable (idempotent). Run as root only so it can install system packages;
the venv and Django steps are executed as the invoking (non-root) user when possible.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "venv"
IS_TTY = sys.stdin.isatty()


class C:
    G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; D = "\033[2m"; X = "\033[0m"


def say(msg): print(f"{C.B}▸{C.X} {msg}")
def ok(msg): print(f"{C.G}✓{C.X} {msg}")
def warn(msg): print(f"{C.Y}!{C.X} {msg}")
def die(msg): print(f"{C.R}✗ {msg}{C.X}"); sys.exit(1)
def run(cmd, **kw):
    print(f"{C.D}$ {' '.join(cmd)}{C.X}")
    return subprocess.run(cmd, check=True, **kw)


def detect_os() -> dict:
    """Return {family, distro, id, pkg} describing the host."""
    sysname = platform.system()
    info = {"family": sysname, "distro": sysname, "id": "", "pkg": None}
    if sysname == "Linux":
        data = {}
        osrel = Path("/etc/os-release")
        if osrel.exists():
            for line in osrel.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k] = v.strip().strip('"')
        info["distro"] = data.get("PRETTY_NAME", "Linux")
        info["id"] = data.get("ID", "")
        like = data.get("ID_LIKE", "")
        if info["id"] in ("debian", "ubuntu") or "debian" in like or "ubuntu" in like:
            info["pkg"] = "apt"
        elif info["id"] in ("fedora", "rhel", "centos", "rocky", "almalinux") or "rhel" in like or "fedora" in like:
            info["pkg"] = "dnf" if shutil.which("dnf") else "yum"
        elif info["id"] in ("arch", "manjaro") or "arch" in like:
            info["pkg"] = "pacman"
        elif info["id"] in ("opensuse", "suse") or "suse" in like:
            info["pkg"] = "zypper"
        elif info["id"] == "alpine":
            info["pkg"] = "apk"
    elif sysname == "Darwin":
        info["distro"] = f"macOS {platform.mac_ver()[0]}"
        info["pkg"] = "brew" if shutil.which("brew") else None
    return info


SYS_PACKAGES = {
    "apt": ["python3-venv", "python3-dev", "build-essential",
            "libpango-1.0-0", "libpangocairo-1.0-0", "libgdk-pixbuf-2.0-0",
            "libffi-dev", "libcairo2"],
    "dnf": ["python3-devel", "gcc", "pango", "cairo", "gdk-pixbuf2", "libffi-devel"],
    "yum": ["python3-devel", "gcc", "pango", "cairo", "gdk-pixbuf2", "libffi-devel"],
    "pacman": ["python", "pango", "cairo", "gdk-pixbuf2", "libffi"],
    "zypper": ["python3-devel", "gcc", "pango", "cairo", "gdk-pixbuf", "libffi-devel"],
    "apk": ["python3-dev", "build-base", "pango", "cairo", "gdk-pixbuf", "libffi-dev"],
    "brew": ["pango", "cairo", "gdk-pixbuf", "libffi"],
}
INSTALL_CMD = {
    "apt": ["apt-get", "install", "-y"],
    "dnf": ["dnf", "install", "-y"],
    "yum": ["yum", "install", "-y"],
    "pacman": ["pacman", "-S", "--noconfirm"],
    "zypper": ["zypper", "install", "-y"],
    "apk": ["apk", "add"],
    "brew": ["brew", "install"],
}
UPDATE_CMD = {"apt": ["apt-get", "update"], "dnf": [], "yum": [],
              "pacman": ["pacman", "-Sy"], "zypper": [], "apk": ["apk", "update"], "brew": []}


def install_system_packages(osinfo) -> None:
    pkg = osinfo["pkg"]
    if not pkg:
        warn("Unknown package manager — skipping system packages. "
             "Install pango/cairo/gdk-pixbuf manually for PDF rendering.")
        return
    say(f"Installing system packages via {pkg} (WeasyPrint dependencies)…")
    if UPDATE_CMD.get(pkg):
        try:
            run(UPDATE_CMD[pkg])
        except subprocess.CalledProcessError:
            warn("package index update failed; continuing")
    try:
        run(INSTALL_CMD[pkg] + SYS_PACKAGES[pkg])
        ok("System packages installed.")
    except subprocess.CalledProcessError:
        warn("Some system packages failed to install — check names for your distro.")


def maybe_install_node(osinfo) -> None:
    """Offer Node.js (only needed for the WhatsApp plugin)."""
    if shutil.which("node"):
        ok(f"Node.js present ({shutil.which('node')}) — WhatsApp plugin can run.")
        return
    if not ask("Install Node.js for the WhatsApp plugin (optional)?", default=False):
        return
    pkg = osinfo["pkg"]
    node_pkg = {"apt": "nodejs", "dnf": "nodejs", "yum": "nodejs", "pacman": "nodejs",
                "zypper": "nodejs", "apk": "nodejs", "brew": "node"}.get(pkg)
    npm_pkg = {"apt": "npm", "dnf": "npm", "pacman": "npm", "apk": "npm"}.get(pkg)
    pkgs = [p for p in (node_pkg, npm_pkg) if p]
    if pkgs:
        try:
            run(INSTALL_CMD[pkg] + pkgs); ok("Node.js installed.")
        except subprocess.CalledProcessError:
            warn("Node.js install failed; install it manually if you need WhatsApp.")


def ask(question: str, default: bool = False) -> bool:
    if not IS_TTY:
        return default
    suffix = "Y/n" if default else "y/N"
    try:
        ans = input(f"{C.Y}?{C.X} {question} [{suffix}] ").strip().lower()
    except EOFError:
        return default
    if not ans:
        return default
    return ans in ("y", "yes")


def drop_privs_user() -> str | None:
    """If invoked via sudo, return the original (non-root) username."""
    return os.environ.get("SUDO_USER") or None


def venv_python() -> Path:
    return VENV / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def as_user(cmd, user: str | None):
    """Run a command as the original user when we are root (so venv isn't root-owned)."""
    if user and os.geteuid() == 0:
        return ["sudo", "-u", user, "-H"] + cmd
    return cmd


def create_venv(user):
    if VENV.exists():
        ok("Virtual environment already exists.")
        return
    say("Creating virtual environment (./venv)…")
    run(as_user([sys.executable, "-m", "venv", str(VENV)], user))
    ok("Virtual environment created.")


def pip_install(user):
    say("Installing Python dependencies…")
    py = str(venv_python())
    run(as_user([py, "-m", "pip", "install", "--upgrade", "pip"], user))
    run(as_user([py, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], user))
    ok("Python dependencies installed.")


def ensure_config(user):
    cfg = ROOT / "config.ini"
    example = ROOT / "config.ini.example"
    if cfg.exists():
        ok("config.ini present.")
    elif example.exists():
        shutil.copy(example, cfg)
        if user and os.geteuid() == 0:
            shutil.chown(cfg, user=user)
        warn("config.ini created from example — edit its values before going live.")
    else:
        warn("config.ini.example not found; skipping.")


def manage(args, user, check=True):
    py = str(venv_python())
    return subprocess.run(as_user([py, str(ROOT / "manage.py")] + args, user),
                          check=check)


def migrate_and_seed(user):
    say("Running migrations…")
    manage(["migrate", "--noinput"], user)
    ok("Migrations applied.")
    say("Seeding roles, menus, search…")
    for cmd in (["seed_roles"], ["seed_menus"], ["rebuild_search"]):
        manage(cmd, user, check=False)
    manage(["compilemessages"], user, check=False)
    ok("Seed data ready.")


def maybe_superuser(user):
    if ask("Create a superuser now?", default=False):
        say("Launching createsuperuser (interactive)…")
        manage(["createsuperuser"], user, check=False)


def main():
    print(f"{C.B}{'='*52}{C.X}")
    print(f"{C.B}  CC Journal — installer{C.X}")
    print(f"{C.B}{'='*52}{C.X}\n")

    osinfo = detect_os()
    ok(f"Detected: {osinfo['distro']} (package manager: {osinfo['pkg'] or 'unknown'})")

    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    user = drop_privs_user()
    if not is_root:
        warn("Not running as root — system packages will be skipped. "
             "Re-run with sudo to install pango/cairo for PDF rendering.")

    if is_root:
        install_system_packages(osinfo)
        maybe_install_node(osinfo)

    create_venv(user)
    pip_install(user)
    ensure_config(user)
    migrate_and_seed(user)
    maybe_superuser(user)

    print()
    ok("CC Journal is installed.")
    print(f"""
{C.D}Next steps:{C.X}
  • Development server:  {C.B}venv/bin/python manage.py runserver{C.X}
  • Production:          {C.B}sudo python3 deploy.py{C.X}   (gunicorn + nginx + systemd)
  • WhatsApp plugin:     {C.B}cd whatsapp_service && npm install{C.X}, then enable it in the admin
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except subprocess.CalledProcessError as e:
        die(f"A command failed (exit {e.returncode}). See output above.")
