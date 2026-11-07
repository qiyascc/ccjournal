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

"""
Yapılandırma servisi — dosya (config.ini) + DB ikilisini yönetir.

  * seed_from_file(): dosyadaki her (section,key) için DB satırı oluşturur (yoksa).
  * Config.get(section,key,default): DB (cache) -> dosya -> default.
  * Config.set(section,key,value): DB + dosya birlikte güncellenir (ikili yazma).
"""
from __future__ import annotations

import configparser
import threading

from django.conf import settings

from .models import SECRET_KEYS, ConfigSetting

_LOCK = threading.Lock()
_CACHE: dict[tuple[str, str], str] | None = None


def _file_path():
    return settings.CONFIG_FILE


def read_file() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    if _file_path().exists():
        cp.read(_file_path(), encoding="utf-8")
    return cp


def write_file(section: str, key: str, value: str) -> None:
    cp = read_file()
    if not cp.has_section(section):
        cp.add_section(section)
    cp.set(section, key, value if value is not None else "")
    with _LOCK, open(_file_path(), "w", encoding="utf-8") as f:
        cp.write(f)


def seed_from_file() -> int:
    """Dosyadaki tüm anahtarları DB'ye tohumlar (yoksa). post_migrate'te çağrılır."""
    cp = read_file()
    n = 0
    for section in cp.sections():
        for key, value in cp.items(section):
            is_secret = (section, key) in SECRET_KEYS
            _, created = ConfigSetting.objects.get_or_create(
                section=section, key=key,
                defaults={"value": value, "is_secret": is_secret},
            )
            n += int(created)
    _invalidate()
    return n


def _invalidate():
    global _CACHE
    _CACHE = None


def _states() -> dict[tuple[str, str], str]:
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = {(r.section, r.key): r.value
                      for r in ConfigSetting.objects.all()}
        except Exception:
            return {}
    return _CACHE


class Config:
    @staticmethod
    def get(section: str, key: str, default=None):
        val = _states().get((section, key))
        if val is not None:
            return val
        cp = read_file()
        try:
            return cp.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    @staticmethod
    def set(section: str, key: str, value: str) -> None:
        """DB + dosyayı birlikte günceller."""
        is_secret = (section, key) in SECRET_KEYS
        ConfigSetting.objects.update_or_create(
            section=section, key=key,
            defaults={"value": value, "is_secret": is_secret},
        )
        write_file(section, key, value)
        _invalidate()
