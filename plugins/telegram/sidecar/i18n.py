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

"""Telegram bot çok-dilli metinleri: Türkçe, İngilizce, Rusça, Çince."""

STRINGS = {
    "en": {
        "start_intro": (
            "👋 *Welcome to {journal}!*\n\n"
            "This bot delivers notifications about your submissions and lets authors "
            "check article status.\n\n"
            "To connect your account, send the token from your profile "
            "(*Start telegram bot*), or open the link there.\n\n"
            "Type /help to see all commands."
        ),
        "help": (
            "*Commands*\n"
            "/start – about this bot\n"
            "/status `<id>` – check the status of your article by its ID\n"
            "/logout – disconnect this Telegram account\n"
            "/help – this message\n\n"
            "To connect: send the token from your profile page."
        ),
        "linked": (
            "✅ *Your account is connected!*\n\n"
            "👤 {name}\n📧 {email}\n🏷 Roles: {roles}\n\n"
            "You will now receive notifications here. Type /help for commands."
        ),
        "already_linked": "✅ This Telegram account is already connected to *{name}*.",
        "bad_token": "❌ Invalid or expired token. Open *Start telegram bot* on your profile and try again.",
        "not_linked": "🔒 This bot only responds to connected accounts. Send your connection token first.",
        "status_usage": "Usage: /status `<article-id>`\nExample: /status 42",
        "status_not_found": "❌ No article with ID `{id}` found among your submissions.",
        "status_line": "📄 *{title}*\nID: `{id}`\nStatus: *{status}*\nStage: {stage}",
        "logout_confirm": "Are you sure you want to disconnect your account from this bot?",
        "logout_yes": "Yes, disconnect",
        "logout_no": "Cancel",
        "logout_done": "👋 Disconnected. This bot will no longer message you.",
        "logout_cancel": "Cancelled. Your account stays connected.",
    },
    "tr": {
        "start_intro": (
            "👋 *{journal}'a hoş geldiniz!*\n\n"
            "Bu bot, gönderileriniz hakkında bildirim iletir ve yazarların makale "
            "durumunu kontrol etmesini sağlar.\n\n"
            "Hesabınızı bağlamak için profilinizdeki *Start telegram bot* "
            "anahtarını gönderin ya da oradaki bağlantıyı açın.\n\n"
            "Tüm komutlar için /help yazın."
        ),
        "help": (
            "*Komutlar*\n"
            "/start – bot hakkında\n"
            "/status `<id>` – makalenizin durumunu ID ile kontrol edin\n"
            "/logout – bu Telegram hesabını ayır\n"
            "/help – bu mesaj\n\n"
            "Bağlanmak için: profil sayfanızdaki anahtarı gönderin."
        ),
        "linked": (
            "✅ *Hesabınız bağlandı!*\n\n"
            "👤 {name}\n📧 {email}\n🏷 Roller: {roles}\n\n"
            "Artık bildirimleri burada alacaksınız. Komutlar için /help."
        ),
        "already_linked": "✅ Bu Telegram hesabı zaten *{name}* hesabına bağlı.",
        "bad_token": "❌ Geçersiz veya süresi dolmuş anahtar. Profilinizden *Start telegram bot*'u açıp tekrar deneyin.",
        "not_linked": "🔒 Bu bot yalnızca bağlı hesaplara yanıt verir. Önce bağlantı anahtarınızı gönderin.",
        "status_usage": "Kullanım: /status `<makale-id>`\nÖrnek: /status 42",
        "status_not_found": "❌ Gönderileriniz arasında `{id}` ID'li makale bulunamadı.",
        "status_line": "📄 *{title}*\nID: `{id}`\nDurum: *{status}*\nAşama: {stage}",
        "logout_confirm": "Hesabınızı bu bottan ayırmak istediğinize emin misiniz?",
        "logout_yes": "Evet, çıkış yap",
        "logout_no": "İptal",
        "logout_done": "👋 Bağlantı kesildi. Bot artık size mesaj göndermeyecek.",
        "logout_cancel": "İptal edildi. Hesabınız bağlı kalıyor.",
    },
    "ru": {
        "start_intro": (
            "👋 *Добро пожаловать в {journal}!*\n\n"
            "Этот бот присылает уведомления о ваших статьях и позволяет авторам "
            "проверять статус публикации.\n\n"
            "Чтобы подключить аккаунт, отправьте токен из профиля "
            "(*Start telegram bot*) или откройте ссылку оттуда.\n\n"
            "Команда /help — список всех команд."
        ),
        "help": (
            "*Команды*\n"
            "/start – о боте\n"
            "/status `<id>` – проверить статус вашей статьи по ID\n"
            "/logout – отключить этот аккаунт Telegram\n"
            "/help – это сообщение\n\n"
            "Для подключения отправьте токен со страницы профиля."
        ),
        "linked": (
            "✅ *Ваш аккаунт подключён!*\n\n"
            "👤 {name}\n📧 {email}\n🏷 Роли: {roles}\n\n"
            "Теперь уведомления будут приходить сюда. Команды: /help."
        ),
        "already_linked": "✅ Этот аккаунт Telegram уже привязан к *{name}*.",
        "bad_token": "❌ Неверный или просроченный токен. Откройте *Start telegram bot* в профиле и повторите.",
        "not_linked": "🔒 Бот отвечает только подключённым аккаунтам. Сначала отправьте токен подключения.",
        "status_usage": "Использование: /status `<id-статьи>`\nПример: /status 42",
        "status_not_found": "❌ Статья с ID `{id}` среди ваших не найдена.",
        "status_line": "📄 *{title}*\nID: `{id}`\nСтатус: *{status}*\nЭтап: {stage}",
        "logout_confirm": "Вы уверены, что хотите отключить аккаунт от бота?",
        "logout_yes": "Да, отключить",
        "logout_no": "Отмена",
        "logout_done": "👋 Отключено. Бот больше не будет писать вам.",
        "logout_cancel": "Отменено. Аккаунт остаётся подключённым.",
    },
    "zh": {
        "start_intro": (
            "👋 *欢迎使用 {journal}！*\n\n"
            "此机器人会推送关于您稿件的通知，并让作者查询文章状态。\n\n"
            "要关联账户，请发送个人资料中的令牌（*Start telegram bot*），或打开那里的链接。\n\n"
            "输入 /help 查看所有命令。"
        ),
        "help": (
            "*命令*\n"
            "/start – 关于本机器人\n"
            "/status `<id>` – 通过 ID 查询文章状态\n"
            "/logout – 断开此 Telegram 账户\n"
            "/help – 本消息\n\n"
            "关联方式：发送个人资料页中的令牌。"
        ),
        "linked": (
            "✅ *您的账户已关联！*\n\n"
            "👤 {name}\n📧 {email}\n🏷 角色：{roles}\n\n"
            "您现在将在此接收通知。输入 /help 查看命令。"
        ),
        "already_linked": "✅ 此 Telegram 账户已关联到 *{name}*。",
        "bad_token": "❌ 令牌无效或已过期。请在个人资料中打开 *Start telegram bot* 重试。",
        "not_linked": "🔒 本机器人仅回复已关联的账户。请先发送您的关联令牌。",
        "status_usage": "用法：/status `<文章ID>`\n示例：/status 42",
        "status_not_found": "❌ 在您的稿件中未找到 ID 为 `{id}` 的文章。",
        "status_line": "📄 *{title}*\nID：`{id}`\n状态：*{status}*\n阶段：{stage}",
        "logout_confirm": "确定要将账户与本机器人断开关联吗？",
        "logout_yes": "是，断开",
        "logout_no": "取消",
        "logout_done": "👋 已断开。机器人将不再向您发送消息。",
        "logout_cancel": "已取消。您的账户仍保持关联。",
    },
}


def t(lang: str, key: str, **kw) -> str:
    lang = (lang or "en")[:2]
    table = STRINGS.get(lang, STRINGS["en"])
    s = table.get(key) or STRINGS["en"].get(key, key)
    return s.format(**kw) if kw else s
