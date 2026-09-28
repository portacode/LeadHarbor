#!/usr/bin/env python3
"""Install services scoped exclusively to this new application."""
from pathlib import Path
import json
from urllib.parse import urlsplit
ROOT = Path('/opt/LeadHarbor')
runtime = json.loads((ROOT/'.private/runtime.json').read_text())
https = urlsplit(runtime['PUBLIC_URL']).scheme == 'https'
# Exposed :8080 is HTTP behind Portacode's HTTPS tunnel. Do not trust arbitrary
# client forwarded headers: this dedicated listener pins the public scheme.
proxy_scheme = 'https' if https else 'http'
nginx = '''server {
    listen 8080 default_server;
    server_name _;
    client_max_body_size 10m;
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto SCHEME;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
'''.replace('SCHEME',proxy_scheme)
# Cloudflare Tunnel is local; restore visitor IP only for that trusted loopback hop.
nginx = nginx.replace('    client_max_body_size', '    set_real_ip_from 127.0.0.1;\n    set_real_ip_from ::1;\n    real_ip_header CF-Connecting-IP;\n    client_max_body_size')
Path('/etc/nginx/conf.d/LeadHarbor.conf').write_text(nginx)
common = '''[Unit]
Description=LeadHarbor LABEL
After=network-online.target postgresql.service
Requires=postgresql.service
[Service]
User=conversion
Group=conversion
WorkingDirectory=/opt/LeadHarbor
Environment=PYTHONUNBUFFERED=1
ExecStart=COMMAND
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/LeadHarbor/media /opt/LeadHarbor/.private
ProtectHome=true
[Install]
WantedBy=multi-user.target
'''
for name,label,command in [('web','web','/opt/LeadHarbor/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 2 --timeout 45'),('worker','analytics worker','/opt/LeadHarbor/.venv/bin/python manage.py run_analytics_worker')]:
    Path(f'/etc/systemd/system/conversion-{name}.service').write_text(common.replace('LABEL',label).replace('COMMAND',command))
Path('/etc/systemd/system/conversion-cleanup.service').write_text('''[Unit]
Description=Expire LeadHarbor analytics
[Service]
Type=oneshot
User=conversion
WorkingDirectory=/opt/LeadHarbor
ExecStart=/opt/LeadHarbor/.venv/bin/python manage.py cleanup_analytics
''')
Path('/etc/systemd/system/conversion-cleanup.timer').write_text('''[Unit]
Description=Daily analytics retention
[Timer]
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
''')
(ROOT/'media').mkdir(exist_ok=True)
