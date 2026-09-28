#!/usr/bin/env bash
set -euo pipefail
cd /opt/LeadHarbor
# Install any new customization dependencies and validate on a disposable database.
.venv/bin/pip install --disable-pip-version-check -r requirements.lock
.venv/bin/python manage.py test --settings=config.test_settings --noinput
.venv/bin/python manage.py makemigrations --check --dry-run --settings=config.test_settings
chown -R conversion:conversion .
runuser -u conversion -- .venv/bin/python manage.py migrate --noinput
# Customizers can create this explicit idempotent data update command.
if [ -f website/management/commands/apply_customization.py ]; then
  runuser -u conversion -- .venv/bin/python manage.py apply_customization
fi
runuser -u conversion -- .venv/bin/python manage.py check --deploy --fail-level WARNING
runuser -u conversion -- .venv/bin/python manage.py collectstatic --noinput
systemctl restart conversion-web conversion-worker
curl --fail --retry 15 --retry-delay 2 --retry-connrefused -H 'Host: localhost' http://127.0.0.1:8080/health/
echo 'Your website is ready. Open the exposed website URL, /admin/ or /dashboard/.'
echo 'Retrieve your unique login from /opt/LeadHarbor/.private/ADMIN-CREDENTIALS.md in the private device file browser.'
