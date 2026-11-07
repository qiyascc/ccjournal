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
FTS5 sanal tablosu (tam-metin arama indeksi).

Django ORM sanal tabloyu yönetmez; raw SQL ile kuruyoruz. Satır anahtarı = submission_id
(rowid). İçerik SearchIndex servisi tarafından yayın/geri-çekme anında güncellenir.
"""
from django.db import connection, migrations


def create_fts(apps, schema_editor):
    if connection.vendor != "sqlite":
        return  # PostgreSQL'e geçilirse ayrı (GIN/tsvector) yol izlenir
    with connection.cursor() as c:
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                title, abstract, keywords, authors,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)


def drop_fts(apps, schema_editor):
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as c:
        c.execute("DROP TABLE IF EXISTS search_index")


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.RunPython(create_fts, drop_fts)]
