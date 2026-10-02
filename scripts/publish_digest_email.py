#!/usr/bin/env python3
"""Deterministic same-date Woods Run Digest Resend publisher.

The script refuses stale, partial, or duplicate content. New broadcasts are
created and sent in one API request. Successful body hashes are written to the
publication ledger so the next issue cannot silently reuse the prior body.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://api.resend.com"
SEGMENT_ID = os.environ.get("WOODS_RUN_SEGMENT_ID", "").strip()
API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
FROM = "Steve Bick | Woods Run Digest <no_reply@forestenterprise.org>"
REPLY_TO = "steve@northeastforests.com"
DENVER = ZoneInfo("America/Denver")
ROOT = Path(__file__).resolve().parents[1]

def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)

def request(method: str, path: str, body: dict | None = None) -> dict:
    if not API_KEY:
        fail("RESEND_API_KEY secret is not configured")
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "WoodsRunDigest/2.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8", "replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        fail(f"Resend HTTP {exc.code}: {exc.read().decode(errors='replace')}")

def latest_issue() -> dict:
    issues = json.loads((ROOT / "data/issues.json").read_text(encoding="utf-8"))
    if not issues:
        fail("data/issues.json is empty")
    issue = issues[0]
    for key in ("date", "displayDate", "url", "summary"):
        if not issue.get(key):
            fail(f"latest issue missing {key}")
    today = datetime.now(DENVER).date().isoformat()
    if issue["date"] != today:
        fail(f"latest canonical issue is {issue['date']}; expected {today}")
    return issue

def canonical_html(issue: dict) -> str:
    y, m, d = issue["date"].split("-")
    path = ROOT / y / m / d / "index.html"
    if not path.exists():
        fail(f"canonical page missing: {path.relative_to(ROOT)}")
    page = path.read_text(encoding="utf-8")
    if len(page) < 3000:
        fail(f"canonical page is suspiciously short ({len(page)} chars)")
    if issue["displayDate"] not in page or issue["url"] not in page:
        fail("canonical page does not match newest issue metadata")
    low = page.lower()
    for marker in ("todo", "placeholder", "lorem ipsum"):
        if marker in low:
            fail(f"canonical page contains placeholder marker: {marker}")
    return page

def strip_tags(value: str) -> str:
    import html as html_lib
    return html_lib.unescape(re.sub(r"<[^>]+>", "", value)).strip()

def email_html(issue: dict, page_html: str) -> str:
    body = page_html.split("<main>",1)[1].split("</main>",1)[0] if "<main>" in page_html else page_html
    body = re.sub(r"<header[\s\S]*?</header>", "", body, flags=re.I)
    body = body.replace('href="/', 'href="https://woodsrun.forestenterprise.org/')
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta http-equiv="X-UA-Compatible" content="IE=edge"></head><body style="margin:0;background-color:#f2eee5;"><table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f2eee5"><tr><td align="center" style="padding-top:24px;padding-right:12px;padding-bottom:24px;padding-left:12px;"><table width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#fffdf8" style="width:100%;max-width:600px;background-color:#fffdf8;"><tr><td style="padding-top:28px;padding-right:30px;padding-bottom:28px;padding-left:30px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:23px;color:#333333;"><p style="font-family:Georgia,'Times New Roman',serif;font-size:28px;line-height:34px;color:#1f3b2b;font-weight:bold;">WOODS RUN DIGEST</p><p style="font-family:Georgia,'Times New Roman',serif;font-size:26px;line-height:32px;color:#222222;">{issue['displayDate']}</p>{body}<p style="font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:18px;color:#777777;"><a href="{{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}" style="color:#777777;">Unsubscribe</a></p></td></tr></table></td></tr></table></body></html>"""

def text_from_html(page: str) -> str:
    import html as html_lib
    text = re.sub(r"<script[\s\S]*?</script>", "", page, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def validate_email(issue: dict, html_body: str, text_body: str) -> str:
    if len(html_body) < 3500:
        fail(f"email HTML is suspiciously short ({len(html_body)} chars)")
    if len(text_body) < 1200:
        fail(f"email text is suspiciously short ({len(text_body)} chars)")
    if issue["displayDate"] not in html_body or issue["displayDate"] not in text_body:
        fail("current date is not present in both email bodies")

    stripped = (html_body + "\n" + text_body).replace("{{{RESEND_UNSUBSCRIBE_URL}}}", "")
    if "{{" in stripped or "}}" in stripped:
        fail("unexpected template marker in email body")

    for href in re.findall(r'href=["\']([^"\']+)["\']', html_body, flags=re.I):
        if href == "{{{RESEND_UNSUBSCRIBE_URL}}}":
            continue
        if not href.startswith("https://"):
            fail(f"non-absolute email link: {href}")

    digest = hashlib.sha256((html_body + "\n" + text_body).encode("utf-8")).hexdigest()
    status_dir = ROOT / "data/publication-status"
    prior = []
    for p in status_dir.glob("*.json"):
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if row.get("date") < issue["date"] and row.get("complete") and row.get("email", {}).get("body_sha256"):
            prior.append(row)
    if prior:
        prior.sort(key=lambda x: x["date"], reverse=True)
        if prior[0]["email"]["body_sha256"] == digest:
            fail("email body hash matches previous completed issue")
    return digest

def write_hash_to_ledger(issue_date: str, digest: str) -> None:
    p = ROOT / "data/publication-status" / f"{issue_date}.json"
    if not p.exists():
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("email", {})["body_sha256"] = digest
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def list_broadcasts() -> list[dict]:
    data = request("GET", "/broadcasts")
    return data.get("data", data if isinstance(data, list) else [])

def poll_sent(broadcast_id: str, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        detail = request("GET", f"/broadcasts/{broadcast_id}")
        last = detail.get("status")
        if last == "sent":
            return
        if last in ("failed", "cancelled"):
            fail(f"broadcast ended in status {last}")
        time.sleep(5)
    fail(f"broadcast did not reach sent within {timeout}s; last status={last}")

def main() -> None:
    if not SEGMENT_ID:
        fail("WOODS_RUN_SEGMENT_ID is missing")

    issue = latest_issue()
    page = canonical_html(issue)
    subject = f"Woods Run Digest — {issue['displayDate']}"
    url = "https://woodsrun.forestenterprise.org" + issue["url"]
    html_body = email_html(issue, page)
    text_body = text_from_html(page) + f"\n\nRead today's edition: {url}"
    body_hash = validate_email(issue, html_body, text_body)

    exact = [b for b in list_broadcasts() if b.get("name") == subject]
    if exact:
        b = exact[0]
        bid = b.get("id")
        if b.get("status") == "sent":
            write_hash_to_ledger(issue["date"], body_hash)
            print(f"Same-date broadcast already sent: {bid}")
            return
        if b.get("status") in ("queued", "scheduled"):
            poll_sent(bid)
            write_hash_to_ledger(issue["date"], body_hash)
            print(f"Same-date broadcast already sent: {bid}")
            return
        detail = request("GET", f"/broadcasts/{bid}")
        content = (detail.get("html") or "") + "\n" + (detail.get("text") or "")
        if issue["displayDate"] not in content or url not in content:
            fail("existing same-date draft failed date/URL validation; refusing stale content")
        request("POST", f"/broadcasts/{bid}/send", {})
        poll_sent(bid)
        write_hash_to_ledger(issue["date"], body_hash)
        print(f"Sent same-date broadcast: {bid}")
        return

    created = request("POST", "/broadcasts", {
        "name": subject,
        "segment_id": SEGMENT_ID,
        "from": FROM,
        "reply_to": [REPLY_TO],
        "subject": subject,
        "preview_text": issue.get("socialText") or issue["summary"],
        "html": html_body,
        "text": text_body,
        "send": True,
    })
    bid = created.get("id")
    if not bid:
        fail(f"broadcast create-and-send returned no id: {created}")
    poll_sent(bid)
    write_hash_to_ledger(issue["date"], body_hash)
    print(f"Sent same-date broadcast: {bid}")

if __name__ == "__main__":
    main()
