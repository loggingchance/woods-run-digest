# Woods Run Digest — production delivery contract

Updated October 13, 2026. All issue dates and daily times use America/Denver.

## Owners and delivery clocks

- The published Site edition is authoritative: https://woodsrun.forestenterprise.org. Custom-domain activation was verified October 13: homepage, archive, dated editions, metadata, subscription page and media return HTTP 200 and match the existing Site.
- Retain https://woods-run-digest.steve760060.chatgpt.site as a working alias without redirects; the private Google Apps Script still uses its existing source configuration.
- This repository holds the faithful dated editorial copy, metadata, generated media, public email payloads and delivery receipts.
- Resend alone schedules and sends email. No GitHub workflow sends email, contains a Resend credential, or acts as the email clock.
- Buffer alone schedules X (ForestBizSchool), Instagram (northeastforests) and YouTube (Logging Chance). GitHub is an advance preparation/handoff mechanism, not a social delivery clock. No GitHub cron is configured.
- Do not introduce Metricool, Render, another paid service, or a Mac dependency.

## Editorial format contract — effective October 15, 2026

- After the edition header, go directly into the lead story. Do not put a recap/list of the day's stories above the stories and then report the same material again below.
- Effective October 22, 2026, remove all FBS takes/perspectives and relabeled commentary from new editions. Immediately after the lead story, before story two, include the canonical `By the Numbers` price tracker: EIA U.S. on-highway diesel (US$/gal, weekly versus prior week), named-contract lumber futures (US$/MBF, latest available close versus same-contract prior-week close), and Madison’s index (US$/MBF, latest reported week versus prior week). Reuse the established EIA series EMD_EPD2D_PTE_NUS_DPG, Investing.com lumber historical data, and madisonsreport.com sources. Include source links and observation/comparison dates; never present stale numbers as current. If a value cannot be verified, keep its source-linked, dated row explicitly unavailable rather than inventing prices or comparisons. Canonical Site README and scripts/issue.py define the markup/validation. The mirror and complete HTML/text email must preserve that block in the same position. Other standalone figures remain optional. Historical issues remain unchanged.
- For future editions beginning October 25, 2026, make story summaries approximately 10–15% shorter than their recent typical length by removing redundancy. Retain key facts, business implications, source qualifications and links; use editorial judgment rather than a rigid word cap. Do not rewrite already published editions.
- Keep the useful editorial flow: lead story, topical/regional sections as warranted, `Action Detector`, and `Under the Radar`. Thursday Deep Dive remains a Thursday feature when due.
- Do not run a standing daily Woods-Ready Safety Plan resource box. Routine house promotion is one single rotation box near the bottom. For new editions beginning October 25, 2026, label it exactly `Today's Featured Resources` (formerly `BOOKS & APPS`).
- The `BOOKS & APPS` rotation is anchored as follows and repeats every five days beginning October 14, 2026: Wet Woods → Timber Tempo → After Wood → Continuous Improvement in Logging → Woods-Ready Safety Plan.
- Every featured item gets a useful one- or two-sentence description explicitly identifying its format (book, app, website, or other accurate format) and its specific, source-supported practical value to a Woods Run reader. Preserve the existing five-item inventory, canonical destinations, rotation anchor and selection logic; inventory expansion is deferred. Never use filler such as “Today’s featured title” or a name/link by itself.
- Preserve these canonical destinations: Wet Woods https://www.amazon.com/dp/B0FP98Y3YN ; Timber Tempo https://www.amazon.com/dp/B0DRYY34KW ; After Wood https://www.amazon.com/dp/B0DRYZLRTF ; Continuous Improvement in Logging https://cinl.loggingchance.com/ ; Woods-Ready Safety Plan https://wrsp.lumbermen.org/.
- Do not advertise remaining Essentials places.

- For future editions, write `strikingText` from an actual substantive story farther down that day's digest, after the headline/lead story. Exclude the headline/lead story, the `By the Numbers` market tracker, navigation, and promotional footers (including `BOOKS & APPS`). Keep the observation faithful to the selected story's verified facts, context, and source; do not invent or exaggerate claims. This changes future striking story selection only: preserve editorial accuracy, visual style, the normal 10:00 AM America/Denver striking schedule, duplicate safeguards, and normal broadcasts. Do not revise existing issues or repost existing content to apply this rule.

## Headline editorial standard — future editions

- Make lead headlines inviting through a concrete, source-supported business consequence or opportunity. Use active, plain language without clickbait, exaggeration or forced slogans. This requires editorial judgment, not a common template for every headline. Keep an existing headline when the proposed rewrite is weaker. The October 19 original, “National Forest Products Week puts new uses for wood in the spotlight”, is the preferred example: do not narrow its scope to webinars or add a slogan. This example guides future choices; do not rewrite the published October 19 issue.
- Spell out non-obvious company and organization abbreviations in headlines, verifying the actual name against authoritative sources: for example, Packaging Corporation of America rather than PCA, and Oak Ridge National Laboratory rather than ORNL. Preserve factual qualifications and avoid implying certainty, scale or opportunity beyond the reporting evidence. Apply the same clarity to story headlines and their media adaptations.
- Author and review the canonical story `article.story h3` and the separate metadata fields together: `cardTeaser` supplies the dominant 1200×630 share-card headline; `cardSubhead` supplies its supporting text; `socialText` supplies the normal X caption (falling back to `summary`). YouTube's title prefers `cardTeaser`, then `socialText`, then `summary`, then the dated digest title. Its description uses `summary`. The Instagram caption is the established dated digest/link text. Reels/Shorts story frames use the story `<h3>` directly, not `cardTeaser`. Keep these adaptations faithful to the same reporting; do not replace the separate non-lead `strikingText` observation with the lead.
- Check the rendered card and video frames before publication. Keep expanded names and essential qualifications readable through concise editorial phrasing and the existing layout, not arbitrary truncation. The current share-card fitting helper can ellipsize overflow, X composition can shorten a caption to its remaining 280-character allowance after the dated URL, and YouTube title composition can shorten to its 100-character platform limit. Do not rely on those fallbacks: revise the source wording to fit in full, inspect the composed text and rendered output, and recheck factual meaning. Video headline fitting raises an error if it cannot fit; resolve the wording without dropping essential qualifications. Platform limits are constraints, not arbitrary editorial word caps. Preserve branding, existing layouts, published issues and old media.

## Standing editorial input — new FBS podcast episodes

- During the existing daily editorial run, check the official The FBS Podcast show by Steve Bick at https://open.spotify.com/show/6D7HFnnYBZXHFdBkirNuQX for newly released episodes. The matching Apple Podcasts show at https://podcasts.apple.com/us/podcast/the-fbs-podcast/id1787404977 can corroborate episode identity and release metadata. Inspect fresh official source metadata; cached search snippets establish show identity but do not prove the latest release list. If freshness or access cannot be verified, report that discovery limitation and retry during the next normal editorial run; do not claim no new episodes or invent a release.
- For new releases from the user's October 23, 2026 America/Denver request onward (October 24 UTC), include each episode once as a concise, source-grounded non-lead mention in the next available Woods Run Digest, unless the user specifies an edition date. Do not backfill the old episode catalog merely because an episode has not appeared in the digest. Before inclusion, check the authoritative published archive and current edition for prior coverage using episode number, normalized title, and canonical episode links/IDs. Treat Spotify and YouTube versions of the same episode as one story, including when the second platform publishes later; do not announce the same episode again. If identity or prior coverage is uncertain, verify before including it.
- Link directly to the verified episode on Spotify and to its matching official YouTube version when available; never guess a video URL. A concise availability mention with the verified title and listening/viewing links is sufficient. Verify any substantive summary against the episode or authoritative episode metadata before adding it. Preserve all existing editorial rules, the `BOOKS & APPS` rotation, and the separate `strikingText` selection rule. Use the existing daily run and publication schedule; do not create another automation or an immediate email/social broadcast for this check.
- User-specified date overrides take precedence: episode 60, “FBS 60 Surviving Hardwood Market Shifts”, remains reserved for Monday, October 26, 2026 under the dated instruction below. Do not include it early or repeat it afterward. That one-edition restriction applies to episode 60; the standing rule continues for subsequent new episodes.

## Dated editorial input — October 26, 2026 only

- In the Monday, October 26, 2026 edition (America/Denver), include a concise non-lead story mentioning the new FBS podcast episode, “FBS 60 Surviving Hardwood Market Shifts”. Include both clean listening/viewing links: Spotify https://open.spotify.com/episode/36SwnUBZhKt94IPmbQlqDo and YouTube https://www.youtube.com/watch?v=WHCddRJ0Xxo. Verify any episode description or detailed claims against the episode or its authoritative metadata before using them; do not invent claims. This is a one-edition inclusion, not a recurring feature, and must not be the headline/lead story. Preserve all standing editorial rules, including the price tracker, `BOOKS & APPS` rotation, and `strikingText` selection rule. Do not apply this instruction to other dates or revise already published editions.

The resource heading change applies to the canonical Site writer/template as well as the mirror and email output. Before preparing the next new edition, ensure the Site's resource renderer and validation use `Today's Featured Resources`; retain existing layout/classes and historical editions. The legacy `BOOKS & APPS` references above name the unchanged rotation and promotional-content exclusions, not the new displayed heading.

## Daily path

1. Site editorial begins 02:30. Editorial handoff checks/mirrors the same edition at03:00, writing the dated page first and data/issues.json last. Never invent a new date on old content.
2. `prepare-assets.yml` responds to the metadata/preparation trigger. It runs regression tests, compiles complete public email content through `prepare_email_payload.py`, and generates/validates media through `prepare_daily_assets.py`. It has no publishing credential.
3. On successful preparation, `daily-publisher.yml` is automatically triggered by `workflow_run`. It reads `data/delivery-policy.json`, validates exact source/media hashes, and runs `delivery_after_prepare.py` / `buffer_queue.py` to queue the three Buffer posts for04:00. No additional scheduled ChatGPT social-trigger write is necessary.
4. The existing private Google Apps Script mailTick runs every five minutes, starts current-date production checks at03:00, reads the complete published Site edition and schedules the normal Resend subscriber broadcast for04:00. mailWatchdog runs every fifteen minutes. The03:30 ChatGPT email task is read-only monitoring. The normal fields preserve the Resend unsubscribe placeholder. Owner-only test fields contain no private recipient tokens.
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
- Duplicate checks traverse Buffer's complete cursor-paginated channel history before creation. Missing pagination evidence, repeated cursors, search limits and ambiguous earlier mutations block another submission. Receipts record the search count, raw provider state, normalized delivery state and separate public verification.
- Do not disable a recurring task because a run failed. Do not bypass a tool permission denial.

## Retained October 8 rehearsal evidence

`E2E-20261008-1600` is a completed historical rehearsal, not a request to restart tests. Its retained receipt records all three Buffer channels sent, matching 22:00 UTC scheduling, and independently verified public URLs. The policy's exact October 8 date cannot authorize another day's test.

The independent email installation's two October 9 owner-only tests were accepted under installation Gaf40a96f5731. Preserve those broadcasts and their passed gates. Prior delivery evidence supports provider readiness; tomorrow's fresh editorial and real queue/outcome checks still determine daily success.

## Regression checks

`python -m unittest discover -s tests -v`

Tests cover date/DST policy, future test isolation, missed deadlines, content/source-link preservation, book rotation, private-token rejection and source/media integrity. Unit-test success does not itself establish provider delivery.


## October 9 final installation repair

The Site published October9 at02:38 Mountain; the repository instead received a different edition at05:10. Preparation now mirrors the exact current published Site via sync_public_editorial.py before compilation. It preserves historical records, fails when the same-date Site is unavailable/incomplete, and records the canonical headlines and links. Do not research competing repository content. The current private Google installation Gaf40a96f5731 is PRODUCTION with both named owner-only tests accepted; preserve it and the private key.

The original illustrated assets/woodsrun-header.webp is tracked and mandatory. A missing file is fatal. Renderer/artwork hashes invalidate obsolete prepared media; routine card generation changes only the latest date. Buffer receipts report requested channels and full daily coverage separately; an X-only recovery cannot establish all-three-channel readiness. A missed scheduling window with incomplete outcomes fails visibly and never falls back to immediate publication.

