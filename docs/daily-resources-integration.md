# Canonical integration and ownership

Effective 2026-10-25. The GitHub mirror does not access the private Sheet, choose
resources or hold the private catalog/cache/ledger. It validates the public
dated selection and copies it to complete email. Do not change repo visibility.

Copy `scripts/daily_resources.py` into the canonical Site source. Keep private
state under a source-only directory such as `private-editorial/resources/`,
outside `dist`, and ensure build/deploy never copies that directory. Do not
commit raw Sheet notes or the full cache/catalog to the GitHub mirror.

During the existing daily canonical run:

1. Reconcile any uncertain prior deployment before selecting a new date: fetch
   the authoritative dated public page and `data/issues.json`. If they match the
   saved prepared selection, validate the resource box and call
   `confirm_publication(date, public_issue, state)`. Otherwise do not mark used;
   retry the same saved date. `prepare` blocks every new date while another date
   is unresolved, even with an empty/exhausted pool. A temporary public read
   failure or a missing confirmation is never proof that publication failed.
   To release a proven-unpublished draft, call `abandon_unpublished(day, state,
   proof=...)` and atomically persist its returned state. Proof requires `date`,
   `outcome: "proven_unpublished"`, `checked_at`, and an `evidence` reference or
   explanation from an independently checked canonical deployment audit. A
   failed/404 public fetch alone is insufficient. Abandonment retains the saved
   choice and audit evidence, consumes no URL, and prohibits reviving that date.
   Never reset history to resolve an ambiguous outcome.
2. Read `daily!A1:B1000` (expand the range if the list grows) through the existing
   authorized Google connection. Pass rows to `refresh`; persist the returned
   last valid snapshot atomically. On transient failure call `refresh(None,
   previous, checked_at=..., error=...)`, preserve the failure flag and continue
   with eligible cached candidates. A header-only successful sheet is empty,
   not an outage. A malformed response is a read failure, not an empty list.
3. Maintain a source-only catalog keyed by `identity(url)`. Entries require
   `title`, `kind`, `description`, `source_url`, and `verified: true`. Use the
   verified metadata supplied by the resource reviewer; never derive claims
   solely from a URL or notes. Newly discovered entries with unverified metadata
   are excluded until verified. No old hardcoded inventory fallback is allowed.
4. Load the durable ledger (initially `{}`). Call `prepare(date, snapshot,
   catalog, state)` and atomically save the returned ledger before rendering.
   This reserves the date's choice but consumes nothing. Use a single serialized
   canonical editor; concurrent or out-of-order publishers are not supported.
5. For future issues only, render `resource_html(selection)` exactly once near
   the bottom and add `featuredResource = public_selection(selection)` to the
   same issue metadata record. This exposes only that day's resource and cache
   flag, never Sheet notes, full catalog or use history. Do not call the legacy
   `book_rotation.featured_item` for these dates. Add shared `validate_feature`
   to canonical validation after parsing the complete edition HTML. Remove
   mandatory Thursday/Deep Dive validation for dates >=2026-10-25 only; preserve
   the existing validation and saved content for earlier dates.
6. Keep draft/build validation separate from deployment. After the canonical
   deployment succeeds, independently read back the public dated HTML and
   metadata, validate their same selection, then call `confirm_publication` and
   atomically persist state in durable canonical source. Local `issue.py publish`
   or a successful build alone must not mark consumption. A crash after public
   deployment is handled by step 1; confirming twice is idempotent.
7. The existing mirror sync takes `featuredResource` with the current canonical
   issue. It checks exact resource title, format, description and URL in the box.
   Email compiles that box unchanged and must not append a second resource.

If a successful snapshot has no eligible entries, use the explicit unavailable
selection/box. Publication may continue, and history is not consumed. Report this
condition to the editor. A date's saved selection stays frozen even if the Sheet
is reordered/edited during a retry; removals affect subsequent new selections.

The no-repeat ledger records successful canonical publication, not emails or
social delivery. Do not consume independently for each channel. Publication
schedules, recipients, branding, podcasts and striking selection are unchanged.

Verification: run `python -m unittest discover -s tests -v` in the mirror test
checkout and the canonical renderer's validation suite after integration. Check
the first Sunday public edition and email share the same `featuredResource`.
No deployment or test send is part of these unit tests.
