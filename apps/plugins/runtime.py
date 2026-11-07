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

"""Yan-süreç (sidecar) yöneticisi — plugin'lerin harici runtime'larını yönetir.

CC Journal çekirdeği Python/Django'dur, ama bazı plugin'ler harici bir runtime
gerektirir (ör. WhatsApp plugin'i Node.js + Baileys). Bu modül böyle süreçleri
başlatır/durdurur/izler. Tasarım hedefleri:

* **Ek servis YOK** — pm2/systemd gerektirmez; süreç doğrudan Django'dan
  `subprocess.Popen` ile başlatılır (kullanıcı isteği: "sunucudan başlatma olmayacak").
* **gunicorn-güvenli** — birden çok worker aynı sidecar'ı başlatmaya çalışmasın diye
  PID dosyası + dosya kilidi ile **tek örnek** garanti edilir.
* **Kalıcı** — süreç arka planda yaşar; Django yeniden başlasa da PID dosyasından
  yeniden bağlanılır (zaten çalışıyorsa tekrar başlatılmaz).

Her sidecar bir `name` ile tanımlanır; durum/PID `var/run/<name>.pid` altında tutulur.
"""
from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

from django.conf import settings

RUN_DIR = Path(settings.BASE_DIR) / "var" / "run"
LOG_DIR = Path(settings.BASE_DIR) / "var" / "log"


def _ensure_dirs():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _pid_file(name: str) -> Path:
    return RUN_DIR / f"{name}.pid"


def _log_file(name: str) -> Path:
    return LOG_DIR / f"{name}.log"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def read_pid(name: str) -> int | None:
    f = _pid_file(name)
    if not f.exists():
        return None
    try:
        pid = int(f.read_text().strip())
    except (ValueError, OSError):
        return None
    return pid if _pid_alive(pid) else None


def is_running(name: str) -> bool:
    return read_pid(name) is not None


def start(name: str, args: list[str], *, cwd: str | None = None,
          env: dict | None = None) -> int:
    """Sidecar'ı başlatır (zaten çalışıyorsa mevcut PID'i döndürür). PID döner.

    `args` tam komut listesidir (ör. ["node", "server.js"]). stdout/stderr log
    dosyasına yönlendirilir; süreç Django'dan bağımsız (detached) yaşar.
    """
    _ensure_dirs()
    existing = read_pid(name)
    if existing:
        return existing

    log = open(_log_file(name), "ab", buffering=0)
    full_env = {**os.environ, **(env or {})}
    kwargs = dict(cwd=cwd, env=full_env, stdout=log, stderr=log,
                  stdin=subprocess.DEVNULL)
    if hasattr(os, "setsid"):
        kwargs["preexec_fn"] = os.setsid
    proc = subprocess.Popen(args, **kwargs)
    _pid_file(name).write_text(str(proc.pid))
    return proc.pid


def stop(name: str, *, timeout: float = 5.0) -> bool:
    """Sidecar'ı durdurur (SIGTERM, sonra SIGKILL). Durduysa True."""
    import time
    pid = read_pid(name)
    f = _pid_file(name)
    if pid is None:
        f.unlink(missing_ok=True)
        return False
    try:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
        deadline = time.time() + timeout
        while time.time() < deadline and _pid_alive(pid):
            time.sleep(0.15)
        if _pid_alive(pid):
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
    finally:
        f.unlink(missing_ok=True)
    return True


def tail_log(name: str, lines: int = 40) -> str:
    f = _log_file(name)
    if not f.exists():
        return ""
    try:
        data = f.read_text(errors="replace").splitlines()
        return "\n".join(data[-lines:])
    except OSError:
        return ""
