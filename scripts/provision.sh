#!/usr/bin/env bash
# Runs ONLY inside the new Portacode device. Never run this on the template author's host.
set -euo pipefail
umask 077
cd /opt/LeadHarbor
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y python3-venv python3-dev libpq-dev postgresql nginx curl git
systemctl enable --now postgresql
id conversion >/dev/null 2>&1 || useradd --system --home-dir /opt/LeadHarbor --shell /usr/sbin/nologin conversion
python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.lock
# Only constant identifiers enter SQL. The app uses local peer authentication.
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='conversion'" | grep -q 1; then
  runuser -u postgres -- createuser conversion
fi
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='conversion'" | grep -q 1; then
  runuser -u postgres -- createdb --owner=conversion conversion
fi
export DATABASE_URL='postgresql:///conversion?host=/var/run/postgresql'
export TRUST_PROXY=true
.venv/bin/python scripts/configure.py
chown -R conversion:conversion .
chmod 755 /opt/LeadHarbor
runuser -u conversion -- .venv/bin/python manage.py migrate --noinput
# runuser preserves optional input variables (no login shell).
.venv/bin/python scripts/import_brand_inputs.py
chown -R conversion:conversion .private
runuser -u conversion -- .venv/bin/python manage.py bootstrap
.venv/bin/python scripts/install_services.py
chown -R conversion:conversion media
chmod 700 media
systemctl daemon-reload
# Validate before exposing the website.
.venv/bin/python manage.py test --settings=config.test_settings --noinput
runuser -u conversion -- .venv/bin/python manage.py check
runuser -u conversion -- .venv/bin/python manage.py collectstatic --noinput
nginx -t
systemctl enable --now conversion-web conversion-worker conversion-cleanup.timer
systemctl reload nginx
curl --fail --retry 15 --retry-delay 2 --retry-connrefused -H "Host: localhost" http://127.0.0.1:8080/health/
echo 'Base site provisioned. The optional customization stage follows.'
