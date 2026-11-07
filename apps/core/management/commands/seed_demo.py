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
"""Demo verisi: "CC Test" dergisi — geniş, çok dilli, PDF'li tam kurulum.

Dört dil (tr/en/ru/az, birincil tr), 3 bölüm, **3 yayınlanmış sayı**, her sayıda
**6 makale** (toplam 18). Her makale akademik biçimde ve uzundur; içerikleri bu
projenin (CC Journal) tüm özelliklerini teknik detaya girmeden anlatır. Her makale
için **PDF galley otomatik üretilir**. Her rol için en az bir kullanıcı ve makale
sayısı kadar yazar kullanıcısı oluşturulur.

Çalıştırma:  python manage.py seed_demo            (varsa eski CC Test'i siler, yeniden kurar)
             python manage.py seed_demo --no-pdf   (PDF üretimini atla — daha hızlı)
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

LOCALES = ["tr", "en", "ru", "az"]
PRIMARY = "tr"

ROLE_USERS = [
    ("Site Administrator", "Aslan", "Məmmədov"), ("Developer", "Qiyas", "CC"),
    ("Journal Manager", "Leyla", "Hüseynova"), ("Editor", "Kamran", "Əliyev"),
    ("Section Editor", "Nigar", "Quliyeva"), ("Guest Editor", "Rəşad", "İsmayılov"),
    ("Reviewer", "Səbinə", "Rəhimova"), ("Author", "Elçin", "Mahmudov"),
    ("Copyeditor", "Günel", "Babayeva"), ("Layout Editor", "Tural", "Cəfərov"),
    ("Proofreader", "Aysel", "Vəliyeva"), ("Translator", "Orxan", "Süleymanov"),
    ("Designer", "Zəhra", "Abbasova"), ("Journal Assistant", "Murad", "Həsənov"),
    ("Subscription Manager", "Lalə", "Kərimova"), ("Reader", "Vüsal", "Nəcəfov"),
]

SECTIONS = [
    {"tr": "Araştırma Makaleleri", "en": "Research Articles", "ru": "Научные статьи", "az": "Araşdırma Məqalələri"},
    {"tr": "Sistem Mimarisi", "en": "Systems Architecture", "ru": "Системная архитектура", "az": "Sistem Memarlığı"},
    {"tr": "Derlemeler ve Değerlendirmeler", "en": "Reviews & Perspectives", "ru": "Обзоры", "az": "İcmallar"},
]

TOPICS = [
    {
        "section": 1,
        "title": {"tr": "Tek Dergi, Birçok Dil: Çok Dilli Akademik Yayıncılık İçin Bir İçerik Modeli",
                  "en": "One Journal, Many Languages: A Content Model for Multilingual Scholarly Publishing",
                  "ru": "Один журнал, много языков: модель многоязычного научного контента",
                  "az": "Bir Jurnal, Çox Dil: Çoxdilli Akademik Nəşr üçün Məzmun Modeli"},
        "lead": {"tr": "Bir derginin içeriğini dört dilde tutarlı sunmak hem editöryal hem teknik bir tasarım sorunudur.",
                 "en": "Presenting a journal across four languages is both an editorial and a design problem.",
                 "ru": "Представление журнала на четырёх языках — задача редакционная и проектная.",
                 "az": "Jurnalı dörd dildə təqdim etmək həm redaksiya, həm dizayn məsələsidir."},
        "paras": {
            "tr": ["Bu çalışma, içeriğin her parçasının — derginin adından bölüm başlıklarına, sayı bilgilerinden makale metinlerine kadar — ayrı bir dilde saklandığı ve sunulduğu bir modeli ele alır. Her içerik nesnesi bir birincil dil taşır; okuyucu seçtiği dilde çeviri bulamazsa sistem sessizce birincil dile döner. Böylece eksik çeviriler, boş bir sayfa yerine anlamlı içerik üretir ve okuyucu deneyimi hiçbir koşulda kopmaz.",
                   "Platform, dil seçimini iki düzeyde ayırır: arayüz menüleri bir dilde, makale metni başka bir dilde olabilir. Bu ayrım, çok uluslu yazar ve okuyucu kitlesi olan dergiler için kritiktir; okuyucu arayüzü ana dilinde kullanırken makaleyi yazıldığı dilde okuyabilir. Elli'den fazla arayüz dili desteklenir ve içerik dilleri dergi düzeyinde yapılandırılır.",
                   "Çeviriler serbest metin yerine tipli tablolarda tutulduğundan; eksik çevirileri raporlamak, belirli bir dildeki tüm başlıkları listelemek veya bir dili topluca eklemek mümkün olur. Bu yapı, çeviri iş akışını öngörülebilir kılar ve derginin zamanla yeni diller eklemesini kolaylaştırır.",
                   "Arama altyapısı da çok dillidir: tam metin arama, makalelerin başlık, öz ve anahtar kelimelerini diller arası tarar. Bir okuyucu Türkçe ararken, İngilizce yazılmış ama Türkçe özü olan bir makaleyi de bulabilir.",
                   "Sonuç olarak çok dillilik, sonradan eklenen bir özellik değil, veri modelinin merkezindeki bir tasarım kararıdır. Bu yaklaşım, derginin uluslararası görünürlüğünü artırırken editöryal iş yükünü öngörülebilir tutar ve dergiyi tek bir dile mahkûm etmez."],
            "en": ["This study presents a model where every piece of content is stored and served per language, with a primary-locale fallback so incomplete translations still produce meaningful pages.",
                   "Language choice is separated at the interface and the content level; over fifty interface languages are supported and content languages are configured per journal.",
                   "Because translations live in typed tables, missing translations can be reported and languages added in bulk.",
                   "Full-text search is multilingual, scanning titles, abstracts and keywords across languages.",
                   "Multilingualism is a design decision at the centre of the data model rather than an afterthought."],
            "ru": ["Каждый элемент содержания хранится отдельно для каждого языка, с откатом к основному языку.",
                   "Выбор языка разделён на уровне интерфейса и содержания; поддерживается более пятидесяти языков интерфейса.",
                   "Полнотекстовый поиск работает на нескольких языках."],
            "az": ["Hər məzmun elementi hər dil üçün ayrıca saxlanılır, tərcümə yoxdursa əsas dilə qayıdılır.",
                   "Dil seçimi interfeys və məzmun səviyyəsində ayrılır; əllidən çox interfeys dili dəstəklənir.",
                   "Tammətnli axtarış çoxdillidir."]},
        "keywords": {"tr": ["çok dillilik", "içerik modeli", "yerelleştirme", "arama"],
                     "en": ["multilingualism", "content model", "localization", "search"],
                     "ru": ["многоязычие", "модель контента", "поиск"],
                     "az": ["çoxdillilik", "məzmun modeli", "axtarış"]},
    },
    {
        "section": 2,
        "title": {"tr": "Tek Kaynaktan Çok Kanala: E-postadan Bağımsız Bildirim Mimarisi",
                  "en": "From One Source to Many Channels: A Mail-Independent Notification Architecture",
                  "ru": "Из одного источника во многие каналы: независимая от почты архитектура уведомлений",
                  "az": "Bir Mənbədən Çox Kanala: E-poçtdan Asılı Olmayan Bildiriş Memarlığı"},
        "lead": {"tr": "Bildirimler yalnızca e-postaya bağlı kaldığında, e-posta yapılandırılmamışsa tüm iletişim durur.",
                 "en": "When notifications depend solely on email, all communication halts if email fails.",
                 "ru": "Когда уведомления зависят только от почты, при сбое почты всё останавливается.",
                 "az": "Bildirişlər yalnız e-poçtdan asılı olduqda, e-poçt nasaz olarsa hər şey dayanır."},
        "paras": {
            "tr": ["Bu makale, bir bildirimin içeriğinin tek bir kaynaktan — paylaşılan şablonlardan — üretildiği ve ardından kayıtlı tüm aktif kanallara dağıtıldığı bir mimari önerir. E-posta artık ayrıcalıklı bir yol değil, yalnızca kanallardan biridir; yanında WhatsApp ve Telegram gibi kanallar eşit konumda durur.",
                   "Her kanal ortak bir arayüzü uygular ve kendi kullanılabilirlik kontrolünü yapar. E-posta yapılandırılmamışsa onun kanalı sessizce devre dışı kalır; diğer kanallar etkilenmeden çalışır. Böylece bir kanalın eksikliği veya hatası diğerlerini durdurmaz; her kanalın başarısı bağımsızdır.",
                   "WhatsApp kanalı, Node.js tabanlı bir yardımcı süreç (sidecar) üzerinden çalışır; Telegram kanalı ise resmi bot arayüzünü kullanır. İki kanal da yöneticinin denetiminde açılıp kapatılabilir ve alıcılar yalnızca açıkça bağlandıklarında mesaj alır.",
                   "Mimari genişlemeye açıktır: gelecekte Slack, SMS veya başka bir kanal eklemek, tek bir kanal sınıfı yazıp kaydetmekten ibarettir. Yeni kanal, mevcut şablonları ve dağıtım mantığını otomatik kullanır; çekirdek kodda değişiklik gerekmez.",
                   "Telegram kanalı, yazarların botla konuşarak makale durumunu sorgulamasına da olanak tanır; bot dört dilde yanıt verir ve yalnızca hesabını bağlamış kullanıcılara cevap verir. Bu, bildirimleri tek yönlü bir kanaldan iki yönlü bir hizmete dönüştürür.",
                   "Bu tasarım, bildirimlerin güvenilirliğini artırır ve dergiyi tek bir iletişim kanalına bağımlı olmaktan kurtarır. Yazarlar bir gönderinin durumu değiştiğinde tercih ettikleri kanaldan haberdar olur."],
            "en": ["This article proposes an architecture where a notification is produced once from shared templates and dispatched to all active channels; email is one channel among several.",
                   "Each channel implements a shared interface and checks its own availability; if email is unconfigured its channel deactivates while others continue.",
                   "The WhatsApp channel runs via a Node.js sidecar; the Telegram channel uses the official bot API; both are toggled by the administrator.",
                   "Adding Slack or SMS later means writing and registering a single class that reuses existing templates.",
                   "The Telegram bot also lets authors query article status in four languages, responding only to linked accounts.",
                   "This improves reliability and frees the journal from depending on a single channel."],
            "ru": ["Уведомление формируется один раз и рассылается по всем активным каналам; почта — один из них.",
                   "Канал WhatsApp работает через вспомогательный процесс, Telegram — через бот.",
                   "Добавление нового канала сводится к одному классу."],
            "az": ["Bildiriş bir dəfə yaradılıb bütün aktiv kanallara göndərilir; e-poçt yalnız biridir.",
                   "WhatsApp kanalı köməkçi proses, Telegram rəsmi bot vasitəsilə işləyir.",
                   "Yeni kanal əlavə etmək bir sinif yazmaqdan ibarətdir."]},
        "keywords": {"tr": ["bildirim", "çok kanallılık", "WhatsApp", "Telegram"],
                     "en": ["notifications", "multi-channel", "WhatsApp", "Telegram"],
                     "ru": ["уведомления", "многоканальность"], "az": ["bildiriş", "çoxkanallılıq"]},
    },
    {
        "section": 1,
        "title": {"tr": "On Altı Rol, Tek İş Akışı: Rol Tabanlı Yetkilendirme ve Kapsam Daraltma",
                  "en": "Sixteen Roles, One Workflow: Role-Based Authorization and Scope Narrowing",
                  "ru": "Шестнадцать ролей, один процесс: ролевая авторизация",
                  "az": "On Altı Rol, Bir İş Axını: Rol Əsaslı İcazələndirmə"},
        "lead": {"tr": "Bir yayın iş akışında editör, hakem, kopya editörü ve yazar çok farklı görünürlük düzeylerine ihtiyaç duyar.",
                 "en": "In a publishing workflow, editors, reviewers, copyeditors and authors need very different visibility.",
                 "ru": "В издательском процессе разные роли требуют разной видимости.",
                 "az": "Nəşr iş axınında müxtəlif rollar fərqli görünürlük tələb edir."},
        "paras": {
            "tr": ["Bu makale, on altı yayıncılık rolünü — Site Yöneticisinden Okuyucuya — kapsayan bir yetkilendirme modelini ele alır. Roller iki sınıfa ayrılır: tam kapsamlı roller (editör, dergi yöneticisi gibi) tüm gönderileri görür; kapsamı daraltılmış roller ise yalnızca atandıkları ya da yazarı oldukları gönderilerle sınırlıdır.",
                   "Kapsam daraltma, yönetim panelinde kendiliğinden uygulanır: bir hakem yalnızca kendisine atanan gönderileri görür, bir yazar yalnızca kendi gönderilerini. Bu, hassas içeriğin yanlış kişilere görünmesini önler ve her rolün arayüzünü sadeleştirir.",
                   "Menü ve araç görünürlüğü de role göre ayarlanır: teknik araçlar (eklentiler, temalar, yapılandırma) yalnızca yönetici ve geliştirici rollerine açıktır. Bir kopya editörü ya da düzeltmen, işine yaramayan menülerle karşılaşmaz.",
                   "Yazarlar, yönetim paneline hiç girmeden kendi gönderilerini ayrı bir 'çalışma alanı' üzerinden takip eder. Bu ayrım, yazar deneyimini editöryal panelden bağımsız ve sade tutar.",
                   "Sonuç olarak yetkilendirme, tek bir bayrakla açılıp kapanan bir özellik değil, her rolün gördüğü veriyi ve aracı belirleyen kapsamlı bir modeldir. Bu model, büyük editöryal ekiplerde bile düzeni ve gizliliği korur."],
            "en": ["This article covers an authorization model spanning sixteen roles, split into full-scope roles that see every submission and scope-narrowed roles limited to what they are assigned or author.",
                   "Scope narrowing is applied automatically in the admin: a reviewer sees only assigned submissions, an author only their own.",
                   "Menu and tool visibility is role-aware; technical tools are restricted to administrator and developer roles.",
                   "Authors track their submissions through a separate workspace without entering the admin at all.",
                   "Authorization is thus a comprehensive model determining what each role sees, not a single switch."],
            "ru": ["Модель охватывает шестнадцать ролей: полный охват и суженный охват.",
                   "Сужение применяется автоматически в админке.",
                   "Видимость меню зависит от роли."],
            "az": ["Model on altı rolu əhatə edir: tam və daraldılmış əhatə.",
                   "Daraltma admin paneldə avtomatik tətbiq olunur.",
                   "Menyu görünürlüyü rola görədir."]},
        "keywords": {"tr": ["yetkilendirme", "roller", "güvenlik", "iş akışı"],
                     "en": ["authorization", "roles", "security", "workflow"],
                     "ru": ["авторизация", "роли"], "az": ["icazələndirmə", "rollar"]},
    },
    {
        "section": 2,
        "title": {"tr": "Kodsuz Dizgi: Sürükle-Bırak Görsel PDF Tasarımcısı",
                  "en": "Typesetting Without Code: A Drag-and-Drop Visual PDF Designer",
                  "ru": "Вёрстка без кода: визуальный конструктор PDF",
                  "az": "Kodsuz Səhifələmə: Sürüklə-burax Vizual PDF Dizayneri"},
        "lead": {"tr": "Yayın üretiminde PDF dizgisi çoğu zaman harici araçlar ve teknik bilgi gerektirir.",
                 "en": "Production typesetting often requires external tools and technical skill.",
                 "ru": "Вёрстка обычно требует внешних инструментов.",
                 "az": "İstehsalat səhifələməsi çox vaxt xarici alətlər tələb edir."},
        "paras": {
            "tr": ["Bu çalışma, makale PDF'lerinin bir sürükle-bırak arayüzüyle tasarlandığı görsel bir tasarımcıyı anlatır. Editör; başlık, öz, yazarlar, künye ve gövde gibi blokları sürükleyerek sıralar, renkleri ve yazı tiplerini seçer, belirli bölümleri gizler — hiç kod yazmadan.",
                   "Tasarım, bir yapılandırma belgesi olarak saklanır ve sunucu tarafında otomatik olarak biçimlendirilmiş bir PDF'e dönüştürülür. Böylece her makale, derginin görsel kimliğine uygun, tutarlı bir PDF olarak üretilir.",
                   "Tasarımcı canlı önizleme sunar: editör bir rengi değiştirdiğinde veya bir bölümü yeniden sıraladığında, sonucu kaydetmeden önce gerçek bir makale üzerinde görebilir. Bu, deneme-yanılmayı hızlandırır ve hata payını azaltır.",
                   "İleri düzey kullanıcılar için tam HTML/CSS kontrolü de mevcuttur; görsel tasarımcı yetmediğinde şablon doğrudan düzenlenebilir. Böylece hem kodsuz hem de tam denetimli iki çalışma biçimi bir arada sunulur.",
                   "Üretilen PDF'ler, yazarların yüklediği Word belgelerinden gelen tabloları ve görselleri de düzgün biçimde taşır. Sonuç, profesyonel görünümlü, indirilebilir bir makale sürümüdür.",
                   "Bu yaklaşım, dizgiyi teknik bir darboğaz olmaktan çıkarır ve küçük editöryal ekiplerin bile yayın kalitesinde PDF üretmesini sağlar."],
            "en": ["This work describes a visual designer where article PDFs are composed by dragging blocks — title, abstract, authors, colophon, body — choosing colours and fonts and hiding sections, all without code.",
                   "The design is stored as a configuration document and rendered server-side into a formatted PDF, consistent with the journal's identity.",
                   "A live preview lets the editor see changes on a real article before saving.",
                   "Advanced users retain full HTML/CSS control when the visual designer is not enough.",
                   "Generated PDFs carry tables and images imported from authors' Word files.",
                   "Typesetting thus stops being a technical bottleneck."],
            "ru": ["Визуальный конструктор позволяет компоновать PDF перетаскиванием блоков без кода.",
                   "Дизайн хранится как документ и рендерится на сервере.",
                   "Доступен предпросмотр и полный контроль HTML/CSS."],
            "az": ["Vizual dizayner PDF-ləri blokları sürükləyərək kodsuz qurur.",
                   "Dizayn sənəd kimi saxlanılır və serverdə render olunur.",
                   "Canlı önizləmə və tam HTML/CSS nəzarəti var."]},
        "keywords": {"tr": ["PDF", "dizgi", "görsel tasarım", "galey"],
                     "en": ["PDF", "typesetting", "visual design", "galley"],
                     "ru": ["PDF", "вёрстка"], "az": ["PDF", "səhifələmə"]},
    },
    {
        "section": 2,
        "title": {"tr": "Tek Zip, Sıfır Sunucu Erişimi: Kendine Yeten Eklenti Mimarisi",
                  "en": "One Zip, Zero Server Access: A Self-Contained Plugin Architecture",
                  "ru": "Один архив, без доступа к серверу: самодостаточные плагины",
                  "az": "Bir Zip, Sıfır Server Girişi: Özünü Təmin Edən Plagin Memarlığı"},
        "lead": {"tr": "Genişletilebilir sistemlerde eklentiler çoğu zaman sunucuya elle dosya kopyalamayı gerektirir.",
                 "en": "In extensible systems, plugins often require manually copying files to the server.",
                 "ru": "В расширяемых системах плагины часто требуют ручной установки.",
                 "az": "Genişlənən sistemlərdə plaginlər çox vaxt əl ilə quraşdırma tələb edir."},
        "paras": {
            "tr": ["Bu makale, bir eklentinin tüm bileşenlerini — kodunu, yardımcı süreçlerini, yönetim şablonlarını ve bildirim kanallarını — tek bir paket içinde taşıdığı bir mimariyi inceler. Yönetici, eklentiyi tek bir zip dosyası olarak yükler ve sistem gerekli kurulum adımlarını otomatik yürütür; sunucuya SSH ile girmeye gerek kalmaz.",
                   "Eklenti paketi bir bildirim dosyası içerir; bu dosya, eklentinin hangi bağımlılıklara ihtiyaç duyduğunu belirtir. Kurulum sırasında sistem, gerekli paketleri (ör. bir yardımcı sürecin bağımlılıkları) otomatik kurar. Böylece teknik olmayan bir yönetici bile karmaşık bir eklentiyi güvenle ekleyebilir.",
                   "Şablon yükleyici, eklentilerin kendi yönetim sayfalarını paket içinden sunmasına olanak tanır; ayrı bir yere dosya kopyalamak gerekmez. Bu, eklentilerin gerçekten taşınabilir olmasını sağlar.",
                   "Aynı yaklaşım temalar için de geçerlidir: bir tema, kendi şablonları ve stilleriyle tek bir zip olarak paketlenip yönetici panelinden yüklenebilir. Tema ve eklenti ekosistemi böylece tutarlı bir kurulum deneyimi paylaşır.",
                   "Mimari, eklentilerin etkinleştirilip devre dışı bırakılmasını da güvenli kılar: bir eklenti kapatıldığında ilgili alanlar ve yardımcı süreçler düzgünce durdurulur. Bu yaşam döngüsü denetimi, sistemi kararlı tutar.",
                   "Sonuç olarak genişletilebilirlik, yalnızca geliştiricilere değil, dergi yöneticilerine de açık bir özellik hâline gelir."],
            "en": ["This article examines an architecture where a plugin carries all its parts — code, sidecars, admin templates, notification channels — in a single package the administrator installs as one zip, with setup steps run automatically.",
                   "A manifest declares the plugin's dependencies, which the system installs automatically at install time.",
                   "A template loader lets plugins serve their own admin pages from within the package.",
                   "The same approach applies to themes, packaged and installed as a single zip from the admin.",
                   "Enabling and disabling are safe; a disabled plugin's fields and sidecars stop cleanly.",
                   "Extensibility thus becomes available to administrators, not just developers."],
            "ru": ["Плагин несёт все части в одном пакете, устанавливаемом как архив, с автоматической настройкой.",
                   "Манифест объявляет зависимости, устанавливаемые автоматически.",
                   "Тот же подход применяется к темам."],
            "az": ["Plagin bütün hissələri bir paketdə daşıyır, admin tərəfindən bir zip kimi quraşdırılır.",
                   "Manifest asılılıqları avtomatik quraşdırır.",
                   "Eyni yanaşma temalara da aiddir."]},
        "keywords": {"tr": ["eklenti", "tema", "kurulum", "genişletilebilirlik"],
                     "en": ["plugins", "themes", "installation", "extensibility"],
                     "ru": ["плагины", "темы"], "az": ["plagin", "tema"]},
    },
    {
        "section": 3,
        "title": {"tr": "Açık Erişim, Kalıcı Kimlik ve Keşfedilebilirlik: Atıf Altyapısı",
                  "en": "Open Access, Persistent Identity and Discoverability: A Citation Infrastructure",
                  "ru": "Открытый доступ, постоянные идентификаторы и обнаружимость",
                  "az": "Açıq Giriş, Daimi Kimlik və Kəşfedilə bilərlik: İstinad İnfrastrukturu"},
        "lead": {"tr": "Bir makalenin uzun ömürlü ve atıf yapılabilir olması, kalıcı kimlikler ve standart üst veri gerektirir.",
                 "en": "An article's longevity and citability depend on persistent identifiers and standard metadata.",
                 "ru": "Долговечность статьи зависит от постоянных идентификаторов и метаданных.",
                 "az": "Məqalənin uzunömürlülüyü daimi identifikatorlardan asılıdır."},
        "paras": {
            "tr": ["Bu derleme, bir dergi platformunun keşfedilebilirlik altyapısını ele alır: kalıcı dijital nesne tanımlayıcıları (DOI), standart üst veri biçimleri ve makine tarafından okunabilir besleme akışları. Her makale, kalıcı bir kimlikle ilişkilendirilir ve bu kimlik makalenin künyesinde açıkça gösterilir.",
                   "Platform, makale üst verisini standart biçimlerde dışa aktarır; bu, dizinleme servislerinin ve diğer sistemlerin içeriği otomatik toplamasına olanak tanır. Üst veri, makalenin başlığını, yazarlarını, özünü ve atıf bilgisini yapılandırılmış biçimde içerir.",
                   "Yapılandırılmış atıf bilgisi, makale sayfasına gömülür; böylece arama motorları ve referans yöneticileri makaleyi doğru biçimde tanır. Okuyucular, atıfı çeşitli biçimlerde kopyalayabilir.",
                   "Site haritaları ve içerik beslemeleri, yeni yayınların hızla keşfedilmesini sağlar. Bir makale yayımlandığında, ilgili akışlar otomatik güncellenir ve dış sistemler değişiklikten haberdar olur.",
                   "Açık erişim politikaları sayı düzeyinde yapılandırılabilir; bir sayı tümüyle açık ya da belirli bir tarihte açılacak biçimde ayarlanabilir. Bu esneklik, farklı yayın modellerini destekler.",
                   "Sonuç olarak keşfedilebilirlik, tek tek özelliklerin toplamı değil, makalenin yaşam döngüsü boyunca kimliğini ve görünürlüğünü koruyan bütünleşik bir altyapıdır."],
            "en": ["This review covers a platform's discoverability infrastructure: persistent identifiers (DOI), standard metadata formats and machine-readable feeds; each article is tied to a persistent identity shown in its colophon.",
                   "The platform exports metadata in standard formats so indexing services can harvest content automatically.",
                   "Structured citation data is embedded in the article page for search engines and reference managers.",
                   "Sitemaps and feeds make new publications quickly discoverable, updating automatically on publication.",
                   "Open-access policies are configurable per issue, fully open or opening on a date.",
                   "Discoverability is thus an integrated infrastructure preserving identity throughout an article's life."],
            "ru": ["Обзор охватывает инфраструктуру обнаружимости: DOI, стандартные метаданные и ленты.",
                   "Метаданные экспортируются в стандартных форматах.",
                   "Политики открытого доступа настраиваются для каждого выпуска."],
            "az": ["İcmal kəşfedilə bilərlik infrastrukturunu əhatə edir: DOI, standart metadata və lentlər.",
                   "Metadata standart formatlarda ixrac olunur.",
                   "Açıq giriş siyasətləri hər buraxılış üçün tənzimlənir."]},
        "keywords": {"tr": ["açık erişim", "DOI", "üst veri", "keşfedilebilirlik"],
                     "en": ["open access", "DOI", "metadata", "discoverability"],
                     "ru": ["открытый доступ", "DOI"], "az": ["açıq giriş", "DOI"]},
    },
]

PART = {"tr": ["I. Kısım", "II. Kısım", "III. Kısım"], "en": ["Part I", "Part II", "Part III"],
        "ru": ["Часть I", "Часть II", "Часть III"], "az": ["I Hissə", "II Hissə", "III Hissə"]}


class Command(BaseCommand):
    help = "Seed a large demo journal ('CC Test'): 3 issues × 6 long articles, with PDFs."

    def add_arguments(self, parser):
        parser.add_argument("--keep", action="store_true", help="Do not delete existing CC Test.")
        parser.add_argument("--no-pdf", action="store_true", help="Skip PDF galley generation (faster).")

    @transaction.atomic
    def handle(self, *args, **opts):
        from django.contrib.auth.models import Group
        from apps.accounts.models import User
        from apps.journals.models import (Journal, JournalTranslation, Section,
                                          SectionTranslation, Issue, IssueTranslation)
        from apps.submissions.models import Submission, SubmissionStatus, Stage
        from apps.publications.models import (Publication, PublicationTranslation,
                                              PublicationStatus, Author, Keyword)
        from apps.core.models.identifiers import Doi

        existing = Journal.objects.filter(path="cc-test").first()
        if existing and not opts["keep"]:
            existing.delete(); self.stdout.write("Removed existing CC Test journal.")
        elif existing:
            self.stdout.write(self.style.WARNING("CC Test exists; --keep set, aborting.")); return

        journal = Journal.objects.create(
            path="cc-test", primary_locale=PRIMARY, supported_locales=LOCALES,
            enabled=True, enable_doi=True, doi_prefix="10.55555", issn_online="2792-1234")
        descs = {"tr": "CC Journal platformunu sergileyen örnek bir akademik dergi.",
                 "en": "A sample academic journal showcasing the CC Journal platform.",
                 "ru": "Образец научного журнала, демонстрирующий платформу CC Journal.",
                 "az": "CC Journal platformasını nümayiş etdirən nümunə akademik jurnal."}
        for loc in LOCALES:
            JournalTranslation.objects.create(journal=journal, locale=loc, title="CC Test",
                                              abbreviation="CCT", description=descs[loc], about=descs[loc])

        sections = []
        for i, sec in enumerate(SECTIONS, start=1):
            s = Section.objects.create(journal=journal, primary_locale=PRIMARY, seq=float(i), abstracts_required=False)
            for loc in LOCALES:
                SectionTranslation.objects.create(section=s, locale=loc, title=sec[loc])
            sections.append(s)

        made_users = 0
        for role, given, family in ROLE_USERS:
            email = f"{_slug(given + '.' + family)}@cc-test.org"
            u = User.objects.filter(email=email).first()
            if not u:
                u = User.objects.create_user(email=email, password="demo12345",
                                             given_name=given, family_name=family, preferred_locale=PRIMARY)
                made_users += 1
            g = Group.objects.filter(name=role).first()
            if g: u.groups.add(g); u.refresh_from_db()

        author_pool = _author_pool(18)
        now = timezone.now()
        total_articles = 0
        pdf_count = 0
        seq_counter = 0

        for issue_idx in range(3):
            year = now.year - (2 - issue_idx)
            issue = Issue.objects.create(
                journal=journal, primary_locale=PRIMARY, volume=issue_idx + 1, number="1",
                year=year, is_published=True, is_current=(issue_idx == 2),
                date_published=now - timezone.timedelta(days=(2 - issue_idx) * 180),
                access=Issue.Access.OPEN)
            for loc in LOCALES:
                vt = {"tr": f"Cilt {issue_idx+1}, Sayı 1", "en": f"Volume {issue_idx+1}, Issue 1",
                      "ru": f"Том {issue_idx+1}, выпуск 1", "az": f"Cild {issue_idx+1}, Nömrə 1"}
                IssueTranslation.objects.create(issue=issue, locale=loc, title=vt[loc])

            for topic_idx, topic in enumerate(TOPICS):
                seq_counter += 1
                sub = Submission.objects.create(journal=journal, locale=PRIMARY,
                                                stage=Stage.PRODUCTION, status=SubmissionStatus.PUBLISHED)
                pub = Publication.objects.create(
                    submission=sub, primary_locale=PRIMARY, section=sections[topic["section"] - 1],
                    issue=issue, seq=float(topic_idx + 1), version_major=1, version_minor=0,
                    status=PublicationStatus.PUBLISHED,
                    date_published=(issue.date_published.date()),
                    license_url="https://creativecommons.org/licenses/by/4.0/")
                for loc in LOCALES:
                    part = PART[loc][issue_idx]
                    title = f"{topic['title'][loc]} — {part}"
                    body = _build_body(topic, loc, part)
                    PublicationTranslation.objects.create(
                        publication=pub, locale=loc, title=title,
                        abstract=topic["lead"][loc], body=body, rights="CC BY 4.0")
                    for kseq, term in enumerate(topic["keywords"][loc]):
                        Keyword.objects.create(publication=pub, locale=loc, term=term, seq=float(kseq))
                try:
                    doi = Doi.objects.create(journal=journal,
                                             doi=f"10.55555/cctest.{year}.{seq_counter}")
                    pub.doi = doi; pub.save(update_fields=["doi"])
                except Exception:
                    pass
                a = author_pool[(seq_counter - 1) % len(author_pool)]
                Author.objects.create(publication=pub, given_name=a[0], family_name=a[1],
                                      email=f"{_slug(a[0]+'.'+a[1])}@cc-test.org",
                                      affiliation=a[2], seq=1.0, orcid=a[3])
                co = author_pool[seq_counter % len(author_pool)]
                Author.objects.create(publication=pub, given_name=co[0], family_name=co[1],
                                      email=f"{_slug(co[0]+'.'+co[1])}@cc-test.org",
                                      affiliation=co[2], seq=2.0)
                sub.current_publication = pub
                sub.save(update_fields=["current_publication"])
                total_articles += 1

                if not opts["no_pdf"]:
                    try:
                        from apps.publications.pdf import generate_pdf_galley
                        generate_pdf_galley(pub, label="PDF", approve=True, replace=True)
                        pdf_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"  PDF skipped for #{seq_counter}: {e}"))

        author_users = 0
        ag = Group.objects.filter(name="Author").first()
        for a in author_pool:
            email = f"{_slug(a[0]+'.'+a[1])}@cc-test.org"
            u = User.objects.filter(email=email).first()
            if not u:
                u = User.objects.create_user(email=email, password="demo12345",
                                             given_name=a[0], family_name=a[1],
                                             affiliation=a[2], orcid=a[3], preferred_locale=PRIMARY)
                author_users += 1
            if ag: u.groups.add(ag); u.refresh_from_db()

        self.stdout.write(self.style.SUCCESS(
            f"Seeded 'CC Test': 3 sections, 3 issues, {total_articles} articles "
            f"({pdf_count} PDFs), {made_users} role users + {author_users} author users, "
            f"4 locales (primary {PRIMARY})."))
        self.stdout.write("All demo accounts use password: demo12345")


def _build_body(topic, loc, part):
    """Uzun, çok paragraflı akademik gövde (HTML). Diğer dillerde mevcut paragraflar."""
    paras = topic["paras"].get(loc) or topic["paras"]["en"]
    head = {"tr": ["Giriş", "Yöntem ve Tasarım", "Tartışma", "Sonuç"],
            "en": ["Introduction", "Method and Design", "Discussion", "Conclusion"],
            "ru": ["Введение", "Метод", "Обсуждение", "Заключение"],
            "az": ["Giriş", "Metod", "Müzakirə", "Nəticə"]}.get(loc)
    closing = {"tr": "Bu bölüm, CC Journal platformunun yukarıda anlatılan yaklaşımını somut bir dergi örneği üzerinde göstermektedir; amaç, akademik yayıncılığın karmaşık gereksinimlerini sade ve sürdürülebilir bir mimariyle karşılamaktır. Gelecek çalışmalar, bu modelin daha büyük ölçekli dergilerde ve farklı disiplinlerde nasıl davrandığını inceleyecektir.",
               "en": "This part demonstrates the platform's approach on a concrete journal example; the aim is to meet the complex requirements of scholarly publishing with a simple, sustainable architecture. Future work will examine how the model behaves at larger scale and across disciplines.",
               "ru": "Эта часть демонстрирует подход платформы на конкретном примере журнала; цель — удовлетворить сложные требования научного издания простой и устойчивой архитектурой.",
               "az": "Bu hissə platformanın yanaşmasını konkret jurnal nümunəsində göstərir; məqsəd akademik nəşrin mürəkkəb tələblərini sadə memarlıqla qarşılamaqdır."}
    out = [f"<p><em>{topic['lead'][loc]} ({part})</em></p>"]
    for i, p in enumerate(paras):
        if i < len(head) and i == 0:
            out.append(f"<h2>{head[0]}</h2>")
        elif i == 1 and len(head) > 1:
            out.append(f"<h2>{head[1]}</h2>")
        elif i == len(paras) - 1 and len(head) > 3:
            out.append(f"<h2>{head[3]}</h2>")
        elif i == 2 and len(head) > 2:
            out.append(f"<h2>{head[2]}</h2>")
        out.append(f"<p>{p}</p>")
    out.append(f"<p>{closing[loc]}</p>")
    return "".join(out)


def _slug(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return "".join(c if c.isalnum() or c == "." else "" for c in s).lower()


def _author_pool(n):
    pool = [
        ("Qiyas", "Sadıqov", "Bakı Dövlət Universiteti", "0000-0002-1825-0097"),
        ("Qiyas", "CC", "CC Journal", "0000-0001-2345-6789"),
        ("Elnur", "Qədirli", "Naxçıvan Dövlət Universiteti", ""),
        ("Aynur", "Məmmədova", "ADA University", "0000-0003-1111-2222"),
        ("Ramil", "Hacıyev", "Khazar University", ""),
        ("Səidə", "Quliyeva", "AMEA", "0000-0002-9999-8888"),
        ("Tofiq", "Əhmədov", "Bakı Mühəndislik Universiteti", ""),
        ("Lamiyə", "Nəbiyeva", "UNEC", ""),
        ("Kənan", "Rüstəmov", "Sumqayıt Dövlət Universiteti", ""),
        ("Pərvin", "Allahverdiyeva", "Gəncə Dövlət Universiteti", ""),
    ]
    i = 0
    while len(pool) < n:
        i += 1
        pool.append((f"Araşdırmaçı{i}", "Test", "CC Test University", ""))
    return pool[:n]
