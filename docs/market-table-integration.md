# Coordinated table cutover (2026-10-27)

Do not activate the canonical output or mirror requirement until the independent
live Google Apps Script formatter has been saved and read back with tested table
preservation. Existing scheduled editions continue on their current format while
that prerequisite is blocked. No manual mailTick, sends or test messages.

Canonical source integration (not completed by this mirror patch):

1. Read the latest canonical source; preserve resource state/catalog and all
   unrelated changes. Copy `scripts/market_table.py`. Replace the three-paragraph
   tracker renderer only for issue dates >=2026-10-27 with
   `render_market_section(date, observations, caveats)`. Retain historical render
   and validation branches for earlier dates. Do not regenerate old dist files.
2. Keep the existing tracker location immediately after the lead. The canonical
   `issue.py` validator must accept the six-row table rather than require three
   old paragraph rows; invoke `validate_market_table(article, date)` after parsing
   the complete edition. Preserve other checks and source/duplicate safeguards.
3. Pass observations keyed by `diesel`, `lumber_futures`, `madisons`,
   `hardwood_ppi`, `housing_starts`, `cad_usd`. Each entry has `status` (verified,
   last_verified or unavailable), `latest`, `observed`, `change` (list of display
   strings), `comparison`, `detail` (units/contract/series context), and `sources`
   (list of label/url pairs). Inputs must come from daily source verification;
   this module is a formatter, not a scraper or price calculator. Missing data
   becomes explicitly dated unavailable; cached observations must be identified
   last_verified. Pass release-specific caveats separately; never reuse the test
   margin of error or dates automatically.
4. HTML contract: `section.by-the-numbers`, heading `By the Numbers`, introductory
   paragraph, `table#market-table`, `colgroup` widths35/33/32%, `thead` headers
   Indicator/Latest/Change, six `tbody > tr` rows each with `th scope=row`, `td`,
   `td`. Dates and details are `span` with inline `display:block`; changes may
   use `br`. Source and caveat paragraphs follow the table. Do not move source
   links into an external-only artifact. Use actual row types/units and current
   named futures contract; no permanently fixed test values.
5. Apps Script must preserve this structure, all cell text and links, and readable
   row-separated plain text. Keep table processing outside the existing p/h
   stripping path, avoiding duplicate processing of nested spans/paragraphs.
   Preserve approved inline styles through sanitization or regenerate their
   fixed safe equivalents. Do not alter its hashing, state, schedules or sends.
6. Verify canonical renderer/validator with the same fixtures, then inspect narrow
   rendered layouts and a full HTML/text compilation without sending. The mirror
   tests verify structural wrapping/percentage constraints, not a screenshot.
   Activate only after live Apps Script compatibility is confirmed. Verify the
   first normal future edition and mirror/email payload preserve six rows and
   source links. Public deployment/readiness is not established by unit tests.

`tests/fixtures/approved_market_table.html` is the table extracted from the actual
approved SENT email message `1a17891d2b6876dd`. Its observations are test fixtures
only; no runtime file uses those numeric values or November2026 as a default.
