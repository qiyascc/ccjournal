# Deploy

Tek komut:

```bash
./deploy.sh                 # venv + bağımlılık + migrate + collectstatic + arama indeksi
python manage.py createsuperuser
./run.sh                    # gunicorn (WhiteNoise statikleri servis eder)
```

Üretim (systemd + nginx):

```bash
sudo cp deploy/ccjournal.service /etc/systemd/system/
sudo systemctl enable --now ccjournal
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/ccjournal
sudo ln -s /etc/nginx/sites-available/ccjournal /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# HTTPS:  sudo certbot --nginx -d ccjournal.example.org
```

`.env` değerlerini (SECRET_KEY, ALLOWED_HOSTS, SITE_URL, e-posta) düzenlemeyi unutmayın.
Celery/Redis yok — e-posta senkron gönderilir, arama SQLite FTS5 ile çalışır.
