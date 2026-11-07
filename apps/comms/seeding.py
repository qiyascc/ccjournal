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
Varsayılan e-posta şablonları.

CURATED: tam çevirisi olan diller (en, az, tr, ru). Diğer tüm OJS dilleri için
İngilizce taban kullanılır (satır oluşturulur, dergi sonradan yerelleştirebilir) —
OJS de eksik locale'de İngilizce'ye düşer.

seed(): apps.core.locales.CONTENT_LOCALES içindeki HER dil için satır oluşturur.
Böylece derginin primary_locale'i ne olursa olsun hazır bir şablon bulunur.
"""
from __future__ import annotations

CURATED: dict[str, dict[str, tuple[str, str]]] = {
    "submission_ack": {
        "en": ("Submission received: {{ title }}",
               "Dear author,\n\nThank you for your submission \"{{ title }}\" to {{ journal }}. "
               "Our editorial team will review it shortly."),
        "az": ("Göndərişiniz qəbul edildi: {{ title }}",
               "Hörmətli müəllif,\n\n\"{{ title }}\" adlı göndərişiniz {{ journal }} jurnalına "
               "qəbul edildi. Redaksiya heyəti tezliklə dəyərləndirəcək."),
        "tr": ("Gönderiniz alındı: {{ title }}",
               "Sayın yazar,\n\n\"{{ title }}\" başlıklı gönderiniz {{ journal }} dergisine "
               "ulaştı. Editör ekibimiz en kısa sürede değerlendirecektir."),
        "ru": ("Материал получен: {{ title }}",
               "Уважаемый автор,\n\nБлагодарим за подачу материала «{{ title }}» в журнал "
               "{{ journal }}. Редакция рассмотрит его в ближайшее время."),
    },
    "editor_new_submission": {
        "en": ("New submission: {{ title }}",
               "A new submission \"{{ title }}\" has been received and awaits assignment."),
        "az": ("Yeni göndəriş: {{ title }}",
               "\"{{ title }}\" adlı yeni göndəriş daxil oldu və təyinat gözləyir."),
        "tr": ("Yeni gönderi: {{ title }}",
               "\"{{ title }}\" başlıklı yeni bir gönderi alındı ve atama bekliyor."),
        "ru": ("Новый материал: {{ title }}",
               "Поступил новый материал «{{ title }}», ожидающий назначения."),
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
        "en": ("Review request", "You have been invited to review a submission. Due: {{ due }}.\n\n"
               "Open the review page: {{ review_url }}"),
        "az": ("Rəy dəvəti", "Bir göndərişi dəyərləndirmək üçün dəvət olundunuz. Son tarix: {{ due }}.\n\n"
               "Rəy səhifəsi: {{ review_url }}"),
        "tr": ("Değerlendirme daveti", "Bir gönderiyi değerlendirmeye davet edildiniz. Son tarih: {{ due }}.\n\n"
               "Değerlendirme sayfası: {{ review_url }}"),
        "ru": ("Приглашение к рецензированию", "Вас пригласили отрецензировать материал. Срок: {{ due }}.\n\n"
               "Страница рецензии: {{ review_url }}"),
    },
    "review_reminder": {
        "en": ("Reminder: review {% if overdue %}overdue{% else %}due {{ due }}{% endif %}",
               "This is a friendly reminder about the review you agreed to complete"
               "{% if overdue %} — it is now overdue (due {{ due }}){% else %} (due {{ due }})"
               "{% endif %}.\n\nOpen the review page: {{ review_url }}\n\n"
               "If you can no longer complete this review, please decline on the same page."),
        "az": ("Xatırlatma: rəy {% if overdue %}gecikib{% else %}son tarix {{ due }}{% endif %}",
               "Dəyərləndirməyi qəbul etdiyiniz göndəriş üçün nəzakətli xatırlatma"
               "{% if overdue %} — son tarix keçib ({{ due }}){% else %} (son tarix {{ due }})"
               "{% endif %}.\n\nRəy səhifəsi: {{ review_url }}"),
        "tr": ("Hatırlatma: değerlendirme {% if overdue %}gecikti{% else %}son tarih {{ due }}{% endif %}",
               "Kabul ettiğiniz değerlendirme için nazik bir hatırlatma"
               "{% if overdue %} — son tarih geçti ({{ due }}){% else %} (son tarih {{ due }})"
               "{% endif %}.\n\nDeğerlendirme sayfası: {{ review_url }}"),
        "ru": ("Напоминание: рецензия {% if overdue %}просрочена{% else %}до {{ due }}{% endif %}",
               "Дружеское напоминание о рецензии, которую вы согласились подготовить"
               "{% if overdue %} — срок истёк ({{ due }}){% else %} (срок {{ due }})"
               "{% endif %}.\n\nСтраница рецензии: {{ review_url }}"),
    },
    "decision_accept": {
        "en": ("Decision on your submission",
               "We are pleased to inform you that your submission has been accepted.\n\n{{ note }}"),
        "az": ("Göndərişiniz haqqında qərar",
               "Göndərişinizin qəbul edildiyini bildirməkdən məmnunuq.\n\n{{ note }}"),
        "tr": ("Gönderiniz hakkında karar",
               "Gönderinizin kabul edildiğini bildirmekten memnuniyet duyarız.\n\n{{ note }}"),
        "ru": ("Решение по вашему материалу",
               "Рады сообщить, что ваш материал принят.\n\n{{ note }}"),
    },
    "decision_decline": {
        "en": ("Decision on your submission",
               "After careful consideration, your submission was not accepted.\n\n{{ note }}"),
        "az": ("Göndərişiniz haqqında qərar",
               "Diqqətlə nəzərdən keçirildikdən sonra göndərişiniz qəbul edilmədi.\n\n{{ note }}"),
        "tr": ("Gönderiniz hakkında karar",
               "Dikkatle değerlendirildikten sonra gönderiniz kabul edilmedi.\n\n{{ note }}"),
        "ru": ("Решение по вашему материалу",
               "После тщательного рассмотрения ваш материал не был принят.\n\n{{ note }}"),
    },
    "decision_revisions": {
        "en": ("Revisions requested",
               "Your submission requires revisions before a final decision.\n\n{{ note }}\n\n"
               "Upload your revised file here: {{ work_url }}"),
        "az": ("Düzəlişlər tələb olunur",
               "Yekun qərardan əvvəl göndərişinizdə düzəlişlər tələb olunur.\n\n{{ note }}\n\n"
               "Düzəliş edilmiş faylı buradan yükləyin: {{ work_url }}"),
        "tr": ("Düzeltme isteniyor",
               "Nihai karardan önce gönderinizde düzeltmeler gerekiyor.\n\n{{ note }}\n\n"
               "Düzeltilmiş dosyanızı buradan yükleyin: {{ work_url }}"),
        "ru": ("Требуются исправления",
               "До окончательного решения требуется доработка материала.\n\n{{ note }}"),
    },
    "publication_published": {
        "en": ("Your article is published: {{ title }}",
               "Congratulations! Your article \"{{ title }}\" is now published in {{ journal }}."),
        "az": ("Məqaləniz dərc olundu: {{ title }}",
               "Təbriklər! \"{{ title }}\" məqaləniz {{ journal }} jurnalında dərc olundu."),
        "tr": ("Makaleniz yayımlandı: {{ title }}",
               "Tebrikler! \"{{ title }}\" makaleniz {{ journal }} dergisinde yayımlandı."),
        "ru": ("Ваша статья опубликована: {{ title }}",
               "Поздравляем! Ваша статья «{{ title }}» опубликована в журнале {{ journal }}."),
    },
    "issue_published": {
        "en": ("New issue: {{ issue }} — {{ journal }}",
               "A new issue of {{ journal }} is now available: {{ issue }}.\n\n"
               "{{ toc }}\n\nRead it here: {{ issue_url }}\n\n"
               "You receive this because you opted in to new-issue notifications. "
               "You can turn it off in your profile: {{ profile_url }}"),
        "az": ("Yeni sayı: {{ issue }} — {{ journal }}",
               "{{ journal }} jurnalının yeni sayısı yayımlandı: {{ issue }}.\n\n"
               "{{ toc }}\n\nOxumaq üçün: {{ issue_url }}\n\n"
               "Bu bildirişi profilinizdə söndürə bilərsiniz: {{ profile_url }}"),
        "tr": ("Yeni sayı: {{ issue }} — {{ journal }}",
               "{{ journal }} dergisinin yeni sayısı yayımlandı: {{ issue }}.\n\n"
               "{{ toc }}\n\nOkumak için: {{ issue_url }}\n\n"
               "Bu bildirimi profilinizden kapatabilirsiniz: {{ profile_url }}"),
        "ru": ("Новый выпуск: {{ issue }} — {{ journal }}",
               "Вышел новый выпуск журнала {{ journal }}: {{ issue }}.\n\n"
               "{{ toc }}\n\nЧитать: {{ issue_url }}\n\n"
               "Отключить уведомления можно в профиле: {{ profile_url }}"),
    },
    "user_invitation": {
        "en": ("Invitation: {{ role }} at {{ journal }}",
               "You have been invited to join {{ journal }} as {{ role }}."
               "{% if message %}\n\n{{ message }}{% endif %}\n\n"
               "Accept the invitation and set up your account here:\n{{ invite_url }}\n\n"
               "The link is valid for 14 days. If you were not expecting this, "
               "you can ignore this email."),
        "az": ("Dəvət: {{ journal }} — {{ role }}",
               "{{ journal }} jurnalına {{ role }} kimi qoşulmağa dəvət olundunuz."
               "{% if message %}\n\n{{ message }}{% endif %}\n\n"
               "Dəvəti qəbul etmək və hesabınızı qurmaq üçün:\n{{ invite_url }}\n\n"
               "Keçid 14 gün etibarlıdır."),
        "tr": ("Davet: {{ journal }} — {{ role }}",
               "{{ journal }} dergisine {{ role }} olarak katılmaya davet edildiniz."
               "{% if message %}\n\n{{ message }}{% endif %}\n\n"
               "Daveti kabul etmek ve hesabınızı kurmak için:\n{{ invite_url }}\n\n"
               "Bağlantı 14 gün geçerlidir."),
        "ru": ("Приглашение: {{ role }} — {{ journal }}",
               "Вас пригласили присоединиться к журналу {{ journal }} в роли {{ role }}."
               "{% if message %}\n\n{{ message }}{% endif %}\n\n"
               "Принять приглашение и создать аккаунт:\n{{ invite_url }}\n\n"
               "Ссылка действительна 14 дней."),
    },
    "email_verification": {
        "en": ("Verify your email — {{ journal }}",
               "Welcome to {{ journal }}! Please confirm your email address to "
               "activate your account:\n\n{{ verify_url }}\n\n"
               "The link is valid for 3 days. If you did not register, ignore this email."),
        "az": ("E-poçtunuzu təsdiqləyin — {{ journal }}",
               "{{ journal }} jurnalına xoş gəlmisiniz! Hesabınızı aktivləşdirmək üçün "
               "e-poçt ünvanınızı təsdiqləyin:\n\n{{ verify_url }}\n\n"
               "Keçid 3 gün etibarlıdır."),
        "tr": ("E-postanızı doğrulayın — {{ journal }}",
               "{{ journal }} dergisine hoş geldiniz! Hesabınızı etkinleştirmek için "
               "e-posta adresinizi doğrulayın:\n\n{{ verify_url }}\n\n"
               "Bağlantı 3 gün geçerlidir."),
        "ru": ("Подтвердите e-mail — {{ journal }}",
               "Добро пожаловать в {{ journal }}! Подтвердите адрес, чтобы "
               "активировать аккаунт:\n\n{{ verify_url }}\n\n"
               "Ссылка действительна 3 дня."),
    },
}


def seed(EmailTemplate, locales) -> int:
    """Verilen tüm locale'ler için global şablon satırı oluşturur (yoksa)."""
    n = 0
    for key, by_locale in CURATED.items():
        base = by_locale["en"]
        for loc in locales:
            subject, body = by_locale.get(loc, base)
            _, created = EmailTemplate.objects.get_or_create(
                journal=None, key=key, locale=loc,
                defaults={"subject": subject, "body": body},
            )
            n += int(created)
    return n
