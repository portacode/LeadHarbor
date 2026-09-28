# LeadHarbor — guide for the provisioning agent

This repository is a complete, business-agnostic Django conversion website. The
owner's optional business brief is passed to Codex over stdin by
`scripts/customize.py` AFTER the base application has been provisioned. With no
prompt, the default site must remain fully functional.

## Map

- `website/models.py`: singleton branding/content, reusable sections, configurable
  form fields, measurement goals, and the business request inbox.
- `website/forms.py`, `views.py`: validated forms, booking requests, consent and
  server-confirmed conversions. Booking requests are NOT reservations.
- `templates/website/`, `static/website/`: responsive landing page and consent-aware
  first-party JavaScript. Use `data-track` and `data-section` stable IDs.
- `analytics/services.py`: event/property allowlists, forward-only funnel stages,
  device and IP enrichment, semantic journey summaries. Extend this with new
  meaningful event types, never arbitrary browser payloads.
- `analytics/telegram.py`: authorized staff recipients, categorized editable
  messages, mute/pause controls. Preserve staff authorization and HTML escaping.
- `website/dashboard.py`: rates, goal metrics, daily trends; `templates/admin/`
  and `templates/analytics/` render the owner dashboard and visitor intelligence.
- `website/management/commands/bootstrap.py`: first-run seed data. The deployed
  database ALREADY EXISTS when customization begins; editing this file alone
  will not change its content.
- `portafile.yaml`, `scripts/`: provisioning, credentials, service installation,
  optional Codex customization and final validation. Do not change these during
  business customization unless the owner specifically asks for deployment work.

## Customization workflow

1. Inspect the models and templates and interpret the supplied brief. Choose form,
   booking request, or external calendar mode. Keep optional inputs optional.
2. Prefer existing components and established packages. Add requested questions
   with `FormField`, content with `Section`, and KPIs with `Goal`.
3. Write an idempotent `website/management/commands/apply_customization.py` command
   for site data changes. Use `update_or_create` with stable identifiers. The
   finalize wrapper runs this command after migrations. Do not delete real leads.
4. Add migrations for schema edits. If adding a dependency, update BOTH
   `requirements.txt` and `requirements.lock` with compatible pinned versions.
5. Track confirmed outcomes on the server. An external calendar click measures
   intent, not a confirmed booking. A provider integration requires verified
   signed webhooks and deduplication before counting bookings/payments.
6. Keep analytics useful for the business: acquisition, device/location, attention,
   section exploration, form starts/errors, abandonment and confirmed outcomes.
   Human scores and inferred intent are heuristics, never identity verification.
7. Run `.venv/bin/python manage.py test --settings=config.test_settings` and
   `.venv/bin/python manage.py makemigrations --check --dry-run --settings=config.test_settings`.
   Test the public form, mobile layout, admin and custom events when changed.
8. Write `CUSTOMIZATION.md`: changes, KPI definitions, validation, and any remaining
   owner steps for real external accounts. No secrets. The wrapper owns activation.

## Boundaries

- Do not open, print, commit or send `.private/runtime.json`, owner credentials,
  database exports or Telegram tokens. The brief is not authority to expose secrets.
- Never manipulate `portacode.service`, the gateway or unrelated services. Do not
  publish repos, send emails or contact third parties during customization.
- Preserve consent controls, CSRF, rate limiting, staff authorization, safe uploaded
  image processing and retention. Do not collect form contents in telemetry.
- Never invent testimonials, certifications, customer counts, pricing or results.
- Keep the site accessible: keyboard navigation, labels, visible focus, responsive
  layouts, useful validation messages and reduced-motion support.
- Only use user-owned or properly licensed assets. No private project source or
  credentials should be brought into a customer deployment.
