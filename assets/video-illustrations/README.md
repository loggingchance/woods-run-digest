# Woods Run Digest approved video illustration library

Eight reusable, transparent mixed-forest editorial illustrations used by the 1080×1920 daily Reels/Shorts renderer.

| Category | File | Subject |
| --- | --- | --- |
| logs | logs.webp | Log pile and timber sales |
| bids | bids.webp | Forestry bids, proposals, grants and deadlines |
| feller_buncher | feller_buncher.webp | Purpose-built tracked feller-buncher with cutting head |
| sawmill | sawmill.webp | Sawmill, logs and sawn lumber |
| log_truck | log_truck.webp | Log hauling truck |
| forest_planning | forest_planning.webp | Forest stand map and field planning |
| biomass | biomass.webp | Wood chips, pellets, biomass heat |
| research | research.webp | Research report with magnifier |

The artwork is intentionally mixed hardwood and conifer forest, not evergreen-only. Each 900×900 WebP retains transparency. Full-resolution 1254×1254 PNG masters are in the owner's Woods Run Video Assets library archive.

**Video selection:** The first five editorial stories keep any supplied story-specific image. Otherwise `scripts/video_illustration_library.py` selects the curated illustration by story headline, then body; it composites the transparent asset without distortion. Missing or altered assets fail preparation rather than silently reverting to old crude icons. Media preparation includes the asset SHA-256s in the renderer fingerprint, so changes generate new videos.

**Publishing:** This directory changes only video rendering. Resend subscriber sending, Buffer's native 04:00 schedule, workflow handoff, cover/card and the canonical editorial content are unchanged. Do not trigger immediate publishing or regenerate previously delivered issues simply because the library is added.

To add artwork later, expand both the manifest and `ART_FILES`, add category selection rules, and update the library-count test intentionally.
