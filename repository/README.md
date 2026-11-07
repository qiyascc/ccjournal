# repository/

Pristine snapshot of the default project structure.

* Restore automatically: `python manage.py failnow --yes`
* Restore manually (if manage.py itself is broken):
  `tar -xzf repository/snapshot.tar.gz -C .`

Never includes: `config.ini`, `media/`, database files, `staticfiles/`.
