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

from django.db import migrations

TEMPLATES = {
    "submission_ack": {
        "en": ("Submission received: {{ title }}",
               "Dear author,\n\nThank you for your submission \"{{ title }}\" to {{ journal }}. "
               "Our editorial team will review it shortly.\n\nRegards,\n{{ journal }}"),
        "az": ("Göndərişiniz qəbul edildi: {{ title }}",
               "Hörmətli müəllif,\n\n\"{{ title }}\" adlı göndərişiniz {{ journal }} jurnalına "
               "qəbul edildi. Redaksiya heyəti tezliklə dəyərləndirəcək.\n\nHörmətlə,\n{{ journal }}"),
    },
    "editor_new_submission": {
        "en": ("New submission: {{ title }}",
               "A new submission \"{{ title }}\" has been received and awaits assignment."),
        "az": ("Yeni göndəriş: {{ title }}",
               "\"{{ title }}\" adlı yeni göndəriş daxil oldu və təyinat gözləyir."),
    },
    "author_action": {
        "en": ("{{ title }}",
               "There is an update on your submission. Please open your workspace to continue:\n\n{{ work_url }}"),
        "az": ("{{ title }}",
               "Göndərişinizlə bağlı yenilik var. Davam etmək üçün iş sahənizi açın:\n\n{{ work_url }}"),
        "tr": ("{{ title }}",
               "Gönderinizle ilgili bir güncelleme var. Devam etmek için çalışma alanınızı açın:\n\n{{ work_url }}"),
        "ru": ("{{ title }}",
               "Есть обновление по вашему материалу. Откройте рабочую область, чтобы продолжить:\n\n{{ work_url }}"),
    },
    "review_request": {
        "en": ("Review request",
               "You have been invited to review a submission. Due: {{ due }}.\n\n"
               "Open the review page: {{ review_url }}"),
        "az": ("Rəy dəvəti",
               "Bir göndərişi dəyərləndirmək üçün dəvət olundunuz. Son tarix: {{ due }}.\n\n"
               "Rəy səhifəsi: {{ review_url }}"),
    },
    "decision_accept": {
        "en": ("Decision on your submission",
               "We are pleased to inform you that your submission has been accepted.\n\n{{ note }}"),
        "az": ("Göndərişiniz haqqında qərar",
               "Göndərişinizin qəbul edildiyini bildirməkdən məmnunuq.\n\n{{ note }}"),
    },
    "decision_decline": {
        "en": ("Decision on your submission",
               "After careful consideration, your submission was not accepted.\n\n{{ note }}"),
        "az": ("Göndərişiniz haqqında qərar",
               "Diqqətlə nəzərdən keçirildikdən sonra göndərişiniz qəbul edilmədi.\n\n{{ note }}"),
    },
    "decision_revisions": {
        "en": ("Revisions requested",
               "Your submission requires revisions before a final decision.\n\n{{ note }}\n\n"
               "Upload your revised file here: {{ work_url }}"),
        "az": ("Düzəlişlər tələb olunur",
               "Yekun qərardan əvvəl göndərişinizdə düzəlişlər tələb olunur.\n\n{{ note }}\n\n"
               "Düzəliş edilmiş faylı buradan yükləyin: {{ work_url }}"),
    },
    "publication_published": {
        "en": ("Your article is published: {{ title }}",
               "Congratulations! Your article \"{{ title }}\" is now published in {{ journal }}."),
        "az": ("Məqaləniz dərc olundu: {{ title }}",
               "Təbriklər! \"{{ title }}\" məqaləniz {{ journal }} jurnalında dərc olundu."),
    },
}


def seed(apps, schema_editor):
    EmailTemplate = apps.get_model("comms", "EmailTemplate")
    for key, locales in TEMPLATES.items():
        for locale, (subject, body) in locales.items():
            EmailTemplate.objects.get_or_create(
                journal=None, key=key, locale=locale,
                defaults={"subject": subject, "body": body},
            )


def unseed(apps, schema_editor):
    EmailTemplate = apps.get_model("comms", "EmailTemplate")
    EmailTemplate.objects.filter(journal__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("comms", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
