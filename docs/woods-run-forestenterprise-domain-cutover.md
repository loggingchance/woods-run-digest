# Woods Run Digest — safe custom-domain cutover

**Target:** https://woodsrun.forestenterprise.org/ and its https://woodsrun.forestenterprise.org/archive/ permanent archive, using the EXISTING Woods Run ChatGPT Site (site ID appgprj_6ac6591c62288191a30bcc4fa545712f). Existing publicly advertised Site origin: https://woods-run-digest.steve760060.chatgpt.site. **Do not create a new Site, second archive, separate hosting service, or competing editorial system.**

## Phase 1: activate the existing Site's actual domain

In ChatGPT Work / Sites, open the existing Woods Run Site and select Site settings → Add domain. Enter `woodsrun.forestenterprise.org`, copy the exact DNS record(s) displayed by Sites, and add those records for host `woodsrun` at the domain's DNS provider. Historical provider for `forestenterprise.org` is GoDaddy; verify this remains true before editing. Preserve all apex/@ and www records, email MX/SPF/DKIM/DMARC, other subdomains, and Resend-domain verification records. Do not invent DNS targets. Refresh the Sites custom-domain status until active and HTTPS valid. If no authenticated owner access or DNS control, report the exact limitation and stop rather than claiming cutover.

GitHub Pages CNAME records are **not** interchangeable with the ChatGPT Sites DNS values; do not point the domain to GitHub Pages when retaining the authoritative ChatGPT Site.

## Phase 2: verify new address before changing working links

Obtain independent public HTTP 200/TLS and correct SAME content on:
- https://woodsrun.forestenterprise.org/
- https://woodsrun.forestenterprise.org/archive/
- https://woodsrun.forestenterprise.org/2026/10/13/
- https://woodsrun.forestenterprise.org/data/issues.json
- https://woodsrun.forestenterprise.org/subscribe/
- https://woodsrun.forestenterprise.org/assets/cards/2026-10-13.png (1200×630)
- https://woodsrun.forestenterprise.org/assets/videos/2026-10-13.mp4 (1080×1920)

Check two older issues, original links, archive pagination/list and live dated-page navigation. Maintain the old ChatGPT Site URL as fallback at least until the 04:00 Mountain morning delivery is demonstrated. If the old URL redirects, take special care: independent Google Apps Script checks public content with `followRedirects:false`, and a sudden 301/302 would prevent newsletter scheduling.

## Phase 3: future-link migration only after Phase 2 passes

Repository: https://github.com/loggingchance/woods-run-digest. Read current SHAs. Update future URL composition consistently and test:
- `scripts/post_to_buffer.py` — SITE_ROOT (X text, Instagram, YouTube)
- `scripts/prepare_email_payload.py` — SITE and inbound URL normalization, preserving source links, four-book rotation and unsubscribe
- `scripts/sync_public_editorial.py` — SITE fetch origin only when new route and no-redirect behavior verified; preserve exact Site editorial source
- `tests/test_email_payload.py` and all domain-sensitive tests
- Authoritative Site's page canonical/OG/sitemap if needed; mirrored `index.html` and `archive/index.html` already use the desired canonical but that proves nothing about DNS
- `README.md` — update deployment status only after proven.

The videos already display `woodsrun.forestenterprise.org` in the footer. Keep accepted past social URLs/Resend broadcasts unchanged and do not republish them.

Run `python -m unittest discover -s tests -v`, render a disposable test video without publishing, and verify current content/media integrity. Do not alter Buffer's 04:00 Mountain daily X/Instagram/YouTube schedule or the separate 10:00 striking post; do not use legacy shareNow, GitHub email/cron, Gmail as sender, Metricool, Render, or paid services. The independent private Google Apps Script under workbenchnf@gmail.com remains the only Resend subscriber-newsletter scheduler; coordinate its Site-root validation only if needed and **do not change its existing installation, triggers, audience or secrets**. A separate October 13 featured-book validation bug also exists and must not be mistaken for the DNS problem.

## Evidence-based completion report

Report (1) verified existing Site custom domain, exact DNS records applied, (2) independently accessible archive + dated article URLs, (3) tests and GitHub commit for link cutover, (4) continued functioning of legacy origin or documented redirect impact, (5) any distinct Google Apps Script email-scheduler blocker. No claim of success before public domain and HTTPS verification.
