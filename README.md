# Woods Run Digest — next-generation publisher

This repository is the clean replacement for `loggingchance/wrdigest`.

## Design

One orchestrator owns the daily state machine:

1. Resolve the issue date in `America/Denver`.
2. Load the same-date issue from `data/issues.json`.
3. Validate the canonical dated page.
4. Build all derived website surfaces from the same issue record.
5. Generate authoritative social assets.
6. Publish only missing delivery components.
7. Verify external delivery and record IDs/links in the daily publication ledger.
8. Re-running the same date is idempotent: completed components are never duplicated.

The old repository remains the production fallback during validation.

## Safety during parallel testing

Scheduled runs start with `WRD_DELIVERY_MODE=dry-run`. In this mode the publisher builds and validates artifacts but does **not** send Resend broadcasts or Buffer posts.

Production cutover requires:
- required credentials configured;
- explicit delivery-mode change to `live`;
- duplicate protection verified;
- at least two consecutive unattended morning cycles verified.

## State

Each date has one ledger:

`data/publication-status/YYYY-MM-DD.json`

The ledger, not workflow history, is the source of truth for recovery.
