# Woods Run Instagram fact cards

Owner authorized November 10, 2026: publish the selected tax card immediately,
then continue fact-based subscription cards twice weekly on days separate from
the established Tuesday/Thursday subscription cards.

## Schedule and isolation
- Fact cards: Wednesday and Friday, 08:00 America/Denver, with DST handled by ZoneInfo.
- Generic subscription cards: existing Tuesday/Thursday 08:00 slots remain unchanged.
- Daily Digest reels and other channels remain unchanged.
- Use the existing Instagram-only workflow and credential; never the daily multi-channel publisher.
- Channel: 6844cc71d6d25b49a1de682e, northeastforests.
- Buffer owns delivery; advance preparation is not publication evidence.
- November 10 immediate tax card is a one-time exception, never a recurring candidate.

## Request schema
Use data/instagram-recruitment-trigger.json with action audit, publish, or verify.
Each scheduled fact item includes:
```json
{
  "slot": "2026-11-11",
  "campaign": "facts",
  "asset": "assets/instagram-recruitment/UNIQUE-NAME.jpg",
  "sha256": "64-character-lowercase-sha256",
  "caption": "The Woods Run Digest. EXACT FACT SENTENCE. Subscribe free — link in bio.",
  "fact": "EXACT FACT SENTENCE.",
  "source_issue": "https://woodsrun.forestenterprise.org/YYYY/MM/DD/",
  "source_url": "https://original-publisher.example/story"
}
```
Placeholders above are explanatory, not a publish request. Fact must appear verbatim
in the caption. Scheduled fact items cannot use immediate mode. Generic items
without campaign retain existing validation and receipts.

## Preparation and evidence
Use an interesting one-sentence fact from an actually published issue, verify the
issue and original source, and preserve dates and material qualifications.
Do not turn a tax deduction into a credit, a proposal into an operating project,
or an expired opportunity into a current one. No invented endorsements.

Artwork: original landscape 3:2 painted Golden Age forestry/wood-products illustration,
consistent with the approved samples; vary scene, season and palette. Include
The Woods Run Digest, the sourced fact, Woods Run Digest subscribers already knew that,
and Subscribe free • Link in bio. Inspect text and image before upload.
Use reviewed unused samples first only after verifying present suitability.

Check complete provider queue/history and all campaign receipts before selecting
a slot or submitting. Persist prepared selections with sources, caption, asset,
hash and slot before handoff; preserve returned provider IDs. Receipts are in
data/instagram-recruitment-receipts/. Do not reset attempt markers, recreate
uncertain submissions, reuse images or repeat a prior fact. Compare wording and
substance, not just filenames. Keep the November 10 tax card consumed.

The two campaigns share one trigger and workflow concurrency group.
Do not overwrite an in-flight request; wait and reconcile its receipt first.
Run python scripts/test_instagram_recruitment.py before publishing.
After handoff verify exact image, caption, channel and time from Buffer readback;
a queued/scheduled post is not yet published. Routine success stays quiet.
Report actionable, unrecoverable failures without claiming publication.
