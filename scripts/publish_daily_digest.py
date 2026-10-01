#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = "https://woodsrun.forestenterprise.org"
DENVER = ZoneInfo("America/Denver")
EASTERN = ZoneInfo("America/New_York")

def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)

def issue_date(value: str | None) -> str:
    if value:
        return value
    return datetime.now(DENVER).date().isoformat()

def load_issues() -> list[dict]:
    p = ROOT / "data/issues.json"
    if not p.exists():
        fail("data/issues.json is missing")
    issues = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(issues, list) or not issues:
        fail("data/issues.json is empty or invalid")
    return sorted(issues, key=lambda x: x["date"], reverse=True)

def find_issue(date: str, issues: list[dict]) -> dict:
    for issue in issues:
        if issue.get("date") == date:
            return issue
    fail(f"No canonical issue metadata exists for {date}")

def dated_path(date: str) -> Path:
    y,m,d = date.split("-")
    return ROOT / y / m / d / "index.html"

def ledger_path(date: str) -> Path:
    return ROOT / "data/publication-status" / f"{date}.json"

def default_ledger(date: str) -> dict:
    return {
        "date": date,
        "mode": os.getenv("WRD_DELIVERY_MODE", "dry-run"),
        "canonical": {"validated": False},
        "build": {
            "homepage": False, "archive": False, "sitemap": False,
            "seo": False, "card": False, "reel": False
        },
        "email": {"status": "pending", "broadcast_id": None, "delivered": 0, "failed": None},
        "social": {
            "x": {"status": "pending", "external_url": None, "post_id": None},
            "instagram": {"status": "pending", "external_url": None, "post_id": None},
            "youtube": {"status": "pending", "external_url": None, "post_id": None}
        },
        "complete": False
    }

def load_ledger(date: str) -> dict:
    p = ledger_path(date)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default_ledger(date)

def save_ledger(ledger: dict) -> None:
    p = ledger_path(ledger["date"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def validate_canonical(issue: dict) -> str:
    p = dated_path(issue["date"])
    if not p.exists():
        fail(f"Canonical page missing: {p.relative_to(ROOT)}")
    page = p.read_text(encoding="utf-8")
    required = [issue["displayDate"], issue["url"]]
    if any(x not in page for x in required):
        fail("Canonical dated page disagrees with data/issues.json")
    return page

def strip_tags(value: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", "", value)).strip()

def ensure_article_schema(issue: dict, page: str) -> tuple[str,bool]:
    if '"@type":"NewsArticle"' in page or '"@type": "NewsArticle"' in page:
        return page, False
    title = (re.search(r"<title>(.*?)</title>", page, re.S) or [None, f"Woods Run Digest — {issue['displayDate']}"])[1]
    desc_match = re.search(r'<meta name="description" content="([^"]*)"', page)
    desc = desc_match.group(1) if desc_match else issue["summary"]
    schema = {
        "@context":"https://schema.org","@type":"NewsArticle",
        "headline":strip_tags(title),"description":html_lib.unescape(desc),
        "datePublished":issue["date"],"dateModified":issue["date"],
        "mainEntityOfPage":{"@type":"WebPage","@id":SITE_ROOT+issue["url"]},
        "image":[f"{SITE_ROOT}/assets/cards/{issue['date']}.png"],
        "publisher":{"@type":"Organization","name":"The Forest Business School","url":"https://www.forestenterprise.org"},
        "isPartOf":{"@type":"WebSite","name":"Woods Run Digest","url":SITE_ROOT+"/"}
    }
    block = '<meta name="robots" content="index,follow,max-image-preview:large"><meta name="author" content="The Forest Business School"><script type="application/ld+json">' + json.dumps(schema,separators=(",",":")).replace("<","\\u003c") + "</script>"
    return page.replace("</head>", block+"</head>", 1), True

def build_surfaces(issue: dict, issues: list[dict], page: str, ledger: dict) -> None:
    page2, changed = ensure_article_schema(issue, page)
    if changed:
        dated_path(issue["date"]).write_text(page2, encoding="utf-8")
    ledger["build"]["seo"] = True

    headlines = [strip_tags(x) for x in re.findall(r"<h3>(.*?)</h3>", page2, re.S)][:3]
    if len(headlines) < 3:
        for x in [issue.get("cardTeaser"), issue.get("strikingText"), issue.get("summary")]:
            if x and x not in headlines:
                headlines.append(x)
            if len(headlines) == 3:
                break
    latest = (
        '<section class="latest-section" aria-labelledby="latest-heading">'
        '<div class="section-heading-row"><div><p class="section-kicker">Latest edition</p>'
        f'<h2 id="latest-heading">{html_lib.escape(issue["displayDate"])}</h2></div>'
        '<span class="edition-date">Daily edition</span></div>'
        '<div class="launch-card latest-callout"><ul class="morning-list">'
        + "".join(f"<li>{html_lib.escape(x)}</li>" for x in headlines)
        + "</ul>"
        f'<a class="read-edition" href="{issue["url"]}">Read the full {html_lib.escape(issue["displayDate"])} edition →</a>'
        "</div></section>"
    )
    hp = ROOT / "index.html"
    home = hp.read_text(encoding="utf-8")
    new_home,n = re.subn(r'<section class="latest-section"[^>]*>.*?</section>', latest, home, count=1, flags=re.S)
    if n != 1: fail("Homepage latest-section not found")
    hp.write_text(new_home, encoding="utf-8")
    ledger["build"]["homepage"] = True

    items=[]
    for i in issues:
        items.append(
            f'<article class="archive-item"><time datetime="{i["date"]}">{html_lib.escape(i["displayDate"])}</time>'
            f'<h2><a href="{i["url"]}">{html_lib.escape(i["displayDate"])}</a></h2>'
            f'<a class="archive-link" href="{i["url"]}">Read edition →</a>'
            f'<p>{html_lib.escape(i.get("summary",""))}</p></article>'
        )
    ap = ROOT / "archive/index.html"
    archive = ap.read_text(encoding="utf-8")
    section = '<section class="archive-list" data-archive-list aria-live="polite">'+"".join(items)+"</section>"
    new_archive,n = re.subn(r'<section class="archive-list"[^>]*>.*?</section>', section, archive, count=1, flags=re.S)
    if n != 1: fail("Archive list not found")
    ap.write_text(new_archive, encoding="utf-8")
    ledger["build"]["archive"] = True

    fixed=[SITE_ROOT+"/",SITE_ROOT+"/archive/",SITE_ROOT+"/research/",SITE_ROOT+"/subscribe/"]
    lines=['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"  <url><loc>{u}</loc></url>" for u in fixed]
    lines += [f'  <url><loc>{SITE_ROOT}{i["url"]}</loc><lastmod>{i["date"]}</lastmod></url>' for i in issues]
    lines.append("</urlset>")
    (ROOT/"sitemap.xml").write_text("\n".join(lines)+"\n",encoding="utf-8")
    ledger["build"]["sitemap"] = True

def run_asset_generators(date: str, ledger: dict) -> None:
    card = ROOT / "assets/cards" / (date + ".png")
    if not card.exists() or card.stat().st_size == 0:
        subprocess.run([sys.executable, "scripts/generate_social_cards.py"], cwd=ROOT, check=True)
    if not card.exists() or card.stat().st_size == 0:
        fail("Social card generator did not produce the dated card")
    ledger["build"]["card"] = True

    reel = ROOT / "assets/videos" / (date + ".mp4")
    if not reel.exists() or reel.stat().st_size == 0:
        subprocess.run([sys.executable, "scripts/render_daily_reel.py"], cwd=ROOT, check=True)
    if not reel.exists() or reel.stat().st_size == 0:
        fail("Reel generator did not produce the dated reel")
    ledger["build"]["reel"] = True

def build(date: str) -> dict:
    issues = load_issues()
    issue = find_issue(date, issues)
    ledger = load_ledger(date)
    ledger["mode"] = os.getenv("WRD_DELIVERY_MODE", ledger.get("mode","dry-run"))
    page = validate_canonical(issue)
    ledger["canonical"]["validated"] = True
    build_surfaces(issue, issues, page, ledger)
    run_asset_generators(date, ledger)
    save_ledger(ledger)
    print(f"BUILD_OK {date}")
    return ledger

def deliver(date: str) -> dict:
    ledger = load_ledger(date)
    mode = os.getenv("WRD_DELIVERY_MODE", "dry-run")
    ledger["mode"] = mode
    if mode != "live":
        for key in ("email",):
            if ledger[key]["status"] == "pending":
                ledger[key]["status"] = "dry-run"
        for key in ("x","instagram","youtube"):
            if ledger["social"][key]["status"] == "pending":
                ledger["social"][key]["status"] = "dry-run"
        save_ledger(ledger)
        print(f"DELIVERY_SKIPPED_DRY_RUN {date}")
        return ledger
    # Live adapters are intentionally gated until staging validation is complete.
    # They will use the ledger's external IDs as duplicate protection and must
    # verify sent/delivered/external URLs before marking complete.
    fail("Live delivery is not enabled in the staging repository yet")

def verify(date: str) -> dict:
    ledger = load_ledger(date)
    build_ok = ledger["canonical"].get("validated") and all(ledger["build"].values())
    if ledger.get("mode") == "dry-run":
        ledger["complete"] = bool(build_ok)
    else:
        email_ok = ledger["email"].get("status") == "delivered" and ledger["email"].get("delivered",0) >= 1 and ledger["email"].get("failed") == 0
        social_ok = all(ledger["social"][k].get("status") == "sent" and ledger["social"][k].get("external_url") for k in ("x","instagram","youtube"))
        ledger["complete"] = bool(build_ok and email_ok and social_ok)
    save_ledger(ledger)
    if not ledger["complete"]:
        fail(f"Verification incomplete for {date}")
    print(f"VERIFY_OK {date}")
    return ledger

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["build","deliver","verify","all"])
    parser.add_argument("--date")
    args=parser.parse_args()
    date=issue_date(args.date)
    if args.command in ("build","all"): build(date)
    if args.command in ("deliver","all"): deliver(date)
    if args.command in ("verify","all"): verify(date)

if __name__=="__main__":
    main()
