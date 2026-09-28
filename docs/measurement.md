# Measurement contract

The event and scalar-property allowlists live in `analytics/services.py`. Browser
telemetry never includes form values, arbitrary DOM text or full referrer URLs.
Paths omit queries/fragments; referral URLs reduce to scheme and hostname.
Campaign values are explicit UTM labels; do not put personal information in them.

`conversion` is server-only and emitted after a valid first-party submission.
`booking_open` is intent. A provider-confirmed booking needs a signed, deduplicated
webhook integration before it can be counted as an outcome. No provider webhook
integration is claimed by the base template.

Dashboard milestone counts are distinct sessions with matching events, not a
strict ordered cohort funnel. Goal rates divide matching sessions by all filtered
sessions. Session filtering uses first-seen time. The daily trend uses visit date.
The UI labels unattributed requests separately (always a 30-day window).

Human score is capped at 100 and comes from browser interaction signals. It is
spoofable and is not bot protection. CSRF, size limits and database-backed rate
limits protect endpoints independently. A signed HttpOnly cookie owns the journey;
client-supplied session identifiers cannot attach to an existing visitor.

Default consent mode waits for explicit permission and respects DNT/GPC.
Declining analytics leaves forms functional. Administrators can disable collection
or choose always-on mode after determining an appropriate legal basis. The owner
must adjust privacy wording and business-request retention to their actual use.

The worker caches location enrichment per public IP via HTTPS to ipwho.is. Provider
availability, rate limits and commercial-use terms must be checked for your plan;
set `GEOIP_ENABLED=false` to disable enrichment. Private/reserved IPs never leave
the service. No country is trusted from arbitrary browser-supplied headers.

Daily cleanup removes expired sessions, events, Telegram delivery records and
orphan IP records after 180 days. Business requests are retained independently,
with their journey link cleared. Delete those from the inbox according to your
business retention policy. Backups and Telegram messages have independent
retention: removing local rows does not delete copies held by those systems.
