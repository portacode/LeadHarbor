#!/usr/bin/env python3
"""Read optional deployment inputs as data, never interpolate them into a shell."""
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent

def configure():
    private = ROOT / '.private'
    private.mkdir(mode=0o700, exist_ok=True)
    private.chmod(0o700)
    runtime_file = private / 'runtime.json'
    existing = json.loads(runtime_file.read_text()) if runtime_file.exists() else {}
    public_url = os.environ.get('PUBLIC_URL') or existing.get('PUBLIC_URL')
    if not public_url:
        exposed_file = Path('/etc/portacode/exposed_services.json')
        raw = os.environ.get('PORTACODE_EXPOSED_SERVICES_JSON')
        if not raw and exposed_file.exists(): raw = exposed_file.read_text()
        payload = json.loads(raw) if raw else []
        services = payload.get('exposed_services', []) if isinstance(payload,dict) else payload
        for service in services:
            if str(service.get('port')) == '8080':
                host = service.get('hostname') or urlsplit(service.get('url','')).hostname
                if host: public_url = 'https://' + host
    public_url = public_url or 'http://localhost:8000'
    parsed = urlsplit(public_url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.path not in {'','/'}:
        raise ValueError('PUBLIC_URL must be a valid HTTP(S) origin without credentials or a path.')
    runtime = {**existing, 'DJANGO_SECRET_KEY':existing.get('DJANGO_SECRET_KEY') or secrets.token_urlsafe(64),
               'PUBLIC_URL':public_url.rstrip('/'), 'ALLOWED_HOSTS':f'{parsed.hostname},localhost,127.0.0.1',
               'ADMIN_USERNAME':existing.get('ADMIN_USERNAME') or 'owner',
               'ADMIN_PASSWORD':existing.get('ADMIN_PASSWORD') or secrets.token_urlsafe(24)}
    for key in ['TELEGRAM_BOT_TOKEN','DATABASE_URL','TRUST_PROXY','GEOIP_ENABLED']:
        if os.environ.get(key): runtime[key] = os.environ[key]
    runtime_file.write_text(json.dumps(runtime, indent=2))
    runtime_file.chmod(0o600)
    # No secrets in the customization brief.
    brief = {key:os.environ.get(key,'') for key in ['BUSINESS_NAME','TAGLINE','HEADLINE','DESCRIPTION','PRIMARY_COLOR','CONVERSION_MODE','BOOKING_URL','CONTACT_EMAIL','AI_PROMPT']}
    (private/'brief.json').write_text(json.dumps(brief,indent=2))
    (private/'brief.json').chmod(0o600)
    print('Private runtime configuration prepared. No credentials printed.')

if __name__ == '__main__': configure()
