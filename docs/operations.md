# Operations

## Deployment contract

`portafile.yaml` targets a fresh Ubuntu 24.04 managed device with systemd, 2 GB RAM,
12 GB disk and an exposed HTTP origin on port 8080. Portacode supplies the public
HTTPS tunnel. Root is used for package/service installation; web and analytics
processes run as the dedicated `conversion` user. PostgreSQL uses local peer
authentication, so there is no shared database password. Gunicorn binds loopback.

The template reads `/etc/portacode/exposed_services.json` (or its documented runtime
environment equivalent) for the public hostname. The device must expose port 8080
through a configured Portacode/Cloudflare tunnel. The last workflow step checks
its exact public `/health/` URL. An unavailable tunnel fails that step rather than
claiming a successful public deployment.

nginx accepts Cloudflare visitor IP information only from the loopback tunnel hop,
then overwrites forwarded headers before passing requests to Gunicorn. Restrict
8080 to your tunnel/firewall policy. Do not reuse this proxy configuration behind
a different topology without updating trust boundaries. Public HTTPS is required
for the production security check. A custom domain requires updating `PUBLIC_URL`
and `ALLOWED_HOSTS` in private runtime configuration and rerunning app checks.

## Processes

```bash
systemctl status conversion-web conversion-worker conversion-cleanup.timer
journalctl -u conversion-web -u conversion-worker --since '1 hour ago'
```

No step restarts or replaces the Portacode device service. The worker is a single
service; do not run multiple copies against the same bot. Provider outages retry
on later worker ticks. Telegram's API has no exactly-once send guarantee: a network
failure immediately after a successful send may produce a duplicate notification.

Secrets are in `.private/runtime.json`, mode 0600. Do not serve the project tree or
commit this directory. Logs must never include bot tokens or customer payloads.
The generated handoff contains the *initial* admin password only. To reset:

```bash
cd /opt/LeadHarbor
runuser -u conversion -- .venv/bin/python manage.py changepassword owner
```

## Backup and restore

Schedule encrypted backups outside the device and verify restores regularly:

```bash
install -d -m 700 /root/conversion-backups
runuser -u postgres -- pg_dump -Fc conversion > /root/conversion-backups/database.dump
tar -czf /root/conversion-backups/private-and-media.tar.gz .private media
```

Store both files privately. Restore into an isolated device first: stop app/worker,
create the `conversion` role/database if needed, use `pg_restore --clean --if-exists`
on the intended database, restore media/runtime files and ownership, migrate,
collect static assets, check security settings, and start the app/worker. Never
point a restore test at a live database. Set up backups before collecting real leads.

## Customization failures

The initial working site is installed before optional Codex changes. A failed
customization or validation reports task failure; inspect private
`.private/customization.log` and `CUSTOMIZATION.md`. The base running process is
not intentionally replaced until final validation passes. Source changes are not
a transactional deployment; restore/revert failed edits before restarting.

To retry, keep `.private/runtime.json` and database intact. Bootstrap creates
content once and never resets the owner's password. Do not manually rerun a full
workflow on an unrelated device. Uploaded input files are task-private; normalized
images are already copied to media by bootstrap.

## Customization credentials

Codex preparation uses Portacode's local device authentication proxy. The prompt is
passed through stdin, never interpolated into shell commands. The wrapper uses
workspace-write sandboxing, a 30-minute limit, and private output logs. Workspace
sandboxing is not a secret-hiding boundary; the provisioning agent is trusted with
this new device and instructed not to read runtime credentials. For hostile briefs,
use a separate secret-free build environment before importing approved changes.
