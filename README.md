# Woods Run Digest — production delivery contract

Updated October 8, 2026. All issue dates and daily times use America/Denver.

## Owners and delivery clocks

- The published Site edition is authoritative: https://woods-run-digest.steve760060.chatgpt.site until custom-domain cutover is actually verified.
- This repository holds the faithful dated editorial copy, metadata, generated media, public email payloads and delivery receipts.
- Resend alone schedules and sends email. No GitHub workflow sends email, contains a Resend credential, or acts as the email clock.
- Buffer alone schedules X (ForestBizSchool), Instagram (northeastforests) and YouTube (Logging Chance). GitHub is an advance preparation/handoff mechanism, not a social delivery clock. No GitHub cron is configured.
- Do not introduce Metricool, Render, another paid service, or a Mac dependency.

## Daily path

1. Site editorial begins 02:30. Editorial handoff checks/mirrors the same edition at03:00, writing the dated page first and data/issues.json last. Never invent a new date on old content.
2. `prepare-assets.yml` responds to the metadata/preparation trigger. It runs regression tests, compiles complete public email content through `prepare_email_payload.py`, and generates/validates media through `prepare_daily_assets.py`. It has no publishing credential.
3. On successful preparation, `daily-publisher.yml` is automatically triggered by `workflow_run`. It reads `data/delivery-policy.json`, validates exact source/media hashes, and runs `delivery_after_prepare.py` / `buffer_queue.py` to queue the three Buffer posts for04:00. No additional scheduled ChatGPT social-trigger write is necessary.
4. The independent Resend email task at03:30 reads `data/email-payloads/YYYY-MM-DD.json` and schedules the full normal subscriber broadcast for04:00. The normal fields preserve the Resend unsubscribe placeholder. Owner-only test fields contain no private recipient tokens.
5. A03:45 readiness monitor checks provider receipts. Buffer native handoff persists its queue receipts before delivery, then reads provider outcomes at due+90seconds and, when needed,due+240seconds. This wait controls verification only; Buffer already owns delivery timing.
6. At04:10 the outcome monitor checks Resend and Buffer separately. At08:10 it also checks the established Tuesday/Friday reports.

## Evidence and failure rules

- `data/preparation/D.json`: source/media hashes and dimensions; not publication.
- `data/email-payloads/D.json`: complete public HTML/text and source links; not an email send receipt.
- `data/buffer-delivery/daily-D.json`: exact normal Buffer IDs, scheduled times and fresh per-channel status.
- `data/buffer-delivery/TEST-ID.json`: distinct authorized test IDs and caption markers. Old daily posts cannot satisfy a new test.
- Resend's actual campaign/email ID, state and events are email evidence. A ChatGPT task, prepared payload or generic tool confirmation is not proof of provider scheduling/delivery.
- `data/publication-status/` and the old `publish_daily_digest.py` overall `complete` flag are legacy records, NOT the current cross-provider source of truth.
- A running Buffer job can be waiting only for its read-only post-due check. Do not duplicate posts to make that job finish sooner.
- Preserve sent, scheduled, processing and ambiguous submissions. Never recreate an ambiguous mutation, force a late immediate send, or treat a late recovery as punctual.
- Native scheduling rejects stale dates, mismatched media, incorrect accounts, ambiguous tests and missed deadlines. Failures must be reported accurately.
- Do not disable a recurring task because a run failed. Do not bypass a tool permission denial.

## Explicit October8 rehearsal

`E2E-20261008-1600` is authorized for16:00 Mountain/22:00UTC. Preparation starts15:35, independent Resend owner-only queue15:40, readiness15:50 and consolidated outcome16:10. The static policy authorizes one new X/Instagram/YouTube test with `[WR TEST E2E-20261008-1600]`. One owner-only email uses subject `WR SYSTEM TEST — October 8, 2026 — E2E-1600` and an exact idempotency key. This is not a subscriber rebroadcast and does not replace tomorrow's04:00 normal identities.

The previous15:00 rehearsal failed to hand off; the09:58 foreground-queued email/Instagram test succeeded. Neither proves this new unattended test or tomorrow's full operation.

## Regression checks

`python -m unittest discover -s tests -v`

Tests cover date/DST policy, future test isolation, missed deadlines, content/source-link preservation, book rotation, private-token rejection and source/media integrity. Unit-test success does not itself establish provider delivery.
