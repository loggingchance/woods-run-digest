#!/usr/bin/env python3
"""Woods Run native Resend scheduler. No ChatGPT task or GitHub Actions sender."""
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Denver")
SEGMENT = "ec27b7e4-84e2-47af-83ce-7d77732ed557"
ROOT = "https://raw.githubusercontent.com/loggingchance/woods-run-digest/main/"
API = "https://api.resend.com"

def request(url, method="GET", payload=None, key=None):
    headers = {"Accept":"application/json", "User-Agent":"WoodsRunResendScheduler/1.0"}
    if key: headers["Authorization"] = "Bearer " + key
    if payload is not None: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        body = err.read(1000).decode(errors="replace")
        raise RuntimeError(f"{method} failed HTTP {err.code}: {body}") from err

def main():
    now = datetime.now(timezone.utc)
    today = now.astimezone(TZ).date()
    due = datetime.combine(today, time(4, 0), TZ).astimezone(timezone.utc)
    if not (due - timedelta(hours=2) <= now < due - timedelta(minutes=3)):
        raise RuntimeError("Outside safe scheduling window; no late, stale, or premature broadcast")
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        raise RuntimeError("RESEND_API_KEY missing")
    date = today.isoformat()
    source = request(ROOT + "data/preparation/" + date + ".json")
    mail = request(ROOT + "data/email-payloads/" + date + ".json")
    expected = "Woods Run Digest — " + today.strftime("%B %-d, %Y")
    if mail.get("date") != date or mail.get("subject") != expected:
        raise RuntimeError("Wrong edition date or subject")
    if not mail.get("links_preserved") or not mail.get("featured_book"):
        raise RuntimeError("Incomplete email payload")
    if not source.get("ready") or not mail.get("source_sha256") or mail["source_sha256"] != source.get("source_sha256"):
        raise RuntimeError("Source hashes do not match")
    html, plain = mail.get("html",""), mail.get("text","")
    if len(html) < 4000 or len(plain) < 2000 or "{{{RESEND_UNSUBSCRIBE_URL}}}" not in html:
        raise RuntimeError("HTML, text or broadcast unsubscribe content missing")
    for url in mail.get("source_urls", []):
        if url not in html:
            raise RuntimeError("Missing source URL in HTML: " + url)
    existing = request(API + "/broadcasts", key=key)
    rows = existing.get("data", [])
    if existing.get("has_more") or existing.get("hasMore"):
        raise RuntimeError("More than 100 broadcasts: cannot safely deduplicate")
    matches = [b for b in rows if b.get("subject")==expected or b.get("name")==expected]
    if matches:
        print(json.dumps({"result":"existing_broadcast_no_mutation","records":[{"id":m.get("id"),"status":m.get("status")} for m in matches]}))
        return
    item = {"segment_id":SEGMENT,"name":expected,"from":"Steve Bick | Woods Run Digest <no_reply@forestenterprise.org>",
            "reply_to":["steve@northeastforests.com"],"subject":expected,"html":html,"text":plain,
            "send":True,"scheduled_at":due.isoformat().replace("+00:00","Z")}
    if os.environ.get("DRY_RUN","1") != "0":
        print(json.dumps({"result":"validated_dry_run","date":date,"subject":expected,"scheduled_at":item["scheduled_at"],"html_length":len(html),"text_length":len(plain)}))
        return
    result = request(API + "/broadcasts","POST",item,key)
    ident = result.get("id")
    if not ident: raise RuntimeError("No broadcast ID returned; inspect provider before any retry")
    request(API + "/broadcasts/" + ident + "/send", "POST", {"scheduled_at": due.isoformat().replace("+00:00","Z")}, key)
    detail = request(API + "/broadcasts/" + ident, key=key)
    print(json.dumps({"result":"provider_record","id":ident,"subject":detail.get("subject"),"status":detail.get("status"),"scheduled_at":detail.get("scheduled_at")}))
    if detail.get("subject") != expected or detail.get("status") not in ("scheduled","queued","sending","sent","delivered"):
        raise RuntimeError("Provider did not confirm expected scheduled broadcast; do not retry automatically")

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print("WOODS_RUN_RESEND_FAILED: " + str(exc), file=sys.stderr)
        sys.exit(1)
