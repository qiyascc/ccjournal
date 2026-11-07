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
Gönderi dosyası iş kuralları.

promote: bir dosyayı sonraki aşamaya "terfi" ettirir; yeni kayıt source_file ile
öncekine zincirlenir (OJS source_submission_file_id mantığı) — denetim izi korunur.
"""
from __future__ import annotations

from .models import SubmissionFile


class FileService:
    @staticmethod
    def promote(file: SubmissionFile, to_stage: int, *, uploader=None) -> SubmissionFile:
        return SubmissionFile.objects.create(
            submission=file.submission,
            file=file.file,
            original_filename=file.original_filename,
            mimetype=file.mimetype,
            file_size=file.file_size,
            file_stage=to_stage,
            genre=file.genre,
            uploader=uploader or file.uploader,
            source_file=file,
            seq=file.seq,
        )
