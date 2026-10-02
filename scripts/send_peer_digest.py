#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
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

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.resend.com"
TZ = ZoneInfo("America/Denver")
HANDOFF = ROOT / "data/handoffs/peer_group.json"
LEDGER_DIR = ROOT / "data/delivery-ledger"
SEGMENT_ID = "6667e0ec-be0f-4f14-a453-e3804c2cfc33"
FROM = "Peer Group Digest <no-reply@forestenterprise.org>"
REPLY_TO = "steve@northeastforests.com"
ALERT_FROM = "Peer Group Digest Monitor <no-reply@forestenterprise.org>"
API_KEY = os.environ.get("RESEND_API_KEY", "").strip()

class ValidationError(Exception):
    pass

def today_iso() -> str:
    return datetime.now(TZ).date().isoformat()

def today_display() -> str:
    d = datetime.now(TZ)
    return f"{d.strftime('%B')} {d.day}, {d.year}"

def request(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict:
    if not API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured")
    data = None if body is None else json.dumps(body).encode("utf-8")
    h = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "PeerGroupDigestPublisher/2.0",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(API + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8", "replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Resend HTTP {exc.code}: {detail}") from exc

def ledger_path(date_iso: str) -> Path:
    return LEDGER_DIR / f"peer-group-{date_iso}.json"

def save_ledger(data: dict) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path(data["date"]).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def current_ledger() -> dict:
    p = ledger_path(today_iso())
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {
        "workflow": "peer-group-digest",
        "date": today_iso(),
        "checked_at": None,
        "handoff_valid": False,
        "body_sha256": None,
        "broadcast_id": None,
        "status": "pending",
        "alert_email_id": None,
        "error": None,
    }

def previous_sent_hash() -> str | None:
    if not LEDGER_DIR.exists():
        return None
    rows = []
    for p in LEDGER_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("date") < today_iso() and data.get("status") == "sent" and data.get("body_sha256"):
            rows.append(data)
    if not rows:
        return None
    rows.sort(key=lambda x: x["date"], reverse=True)
    return rows[0]["body_sha256"]

def normalize_for_hash(p: dict) -> str:
    return (p.get("subject","") + "\n" + p.get("text","") + "\n" + p.get("html","")).strip()

def validate_handoff(p: dict) -> str:
    required = ["date","name","segmentId","from","replyTo","subject","previewText","html","text","send"]
    missing = [k for k in required if k not in p]
    if missing:
        raise ValidationError("missing fields: " + ", ".join(missing))

    expected_display = today_display()
    if p["date"] != expected_display:
        raise ValidationError(f"handoff date is {p['date']!r}; expected {expected_display!r}")
    expected_name = f"Peer Group Digest — {expected_display}"
    if p["name"] != expected_name:
        raise ValidationError("broadcast name/date mismatch")
    if p["subject"] != expected_name:
        raise ValidationError("subject/date mismatch")
    if p["segmentId"] != SEGMENT_ID:
        raise ValidationError("wrong Peer Group Digest segment")
    if p["from"] != FROM:
        raise ValidationError("wrong sender")
    if p["replyTo"] != [REPLY_TO]:
        raise ValidationError("wrong reply-to")
    if p["send"] is not True:
        raise ValidationError("send flag is not true")

    html_body = p["html"]
    text_body = p["text"]
    if len(html_body) < 2500:
        raise ValidationError(f"HTML body too short ({len(html_body)} chars)")
    if len(text_body) < 800:
        raise ValidationError(f"text body too short ({len(text_body)} chars)")

    lower = (html_body + "\n" + text_body).lower()
    for marker in ("todo", "placeholder", "lorem ipsum"):
        if marker in lower:
            raise ValidationError(f"placeholder marker found: {marker}")

    # Resend's unsubscribe token is the only allowed template marker.
    stripped = (html_body + "\n" + text_body).replace("{{{RESEND_UNSUBSCRIBE_URL}}}", "")
    if "{{" in stripped or "}}" in stripped:
        raise ValidationError("unexpected template marker remains")

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_body, flags=re.I)
    for href in hrefs:
        if href == "{{{RESEND_UNSUBSCRIBE_URL}}}":
            continue
        if not href.startswith("https://"):
            raise ValidationError(f"non-absolute email link: {href}")

    if expected_display not in html_body or expected_display not in text_body:
        raise ValidationError("current issue date not present in both bodies")
    if "https://peer.vtfbs.com/" not in html_body:
        raise ValidationError("public issue link missing from HTML")

    digest = hashlib.sha256(normalize_for_hash(p).encode("utf-8")).hexdigest()
    prior = previous_sent_hash()
    if prior and digest == prior:
        raise ValidationError("body hash matches previous sent issue")
    return digest

def list_broadcasts() -> list[dict]:
    data = request("GET", "/broadcasts")
    return data.get("data", data if isinstance(data, list) else [])

def poll_sent(broadcast_id: str, timeout: int = 180) -> str:
    deadline = time.time() + timeout
    last = "unknown"
    while time.time() < deadline:
        detail = request("GET", f"/broadcasts/{broadcast_id}")
        last = detail.get("status", "unknown")
        if last == "sent":
            return last
        if last in {"failed", "cancelled"}:
            raise RuntimeError(f"broadcast ended in status {last}")
        time.sleep(5)
    raise RuntimeError(f"broadcast did not reach sent within {timeout}s; last status={last}")

def alert(message: str, ledger: dict) -> None:
    subject = f"Peer Group Digest — {today_display()} NOT delivered"
    body = {
        "from": ALERT_FROM,
        "to": [REPLY_TO],
        "subject": subject,
        "text": (
            f"The Peer Group Digest was not delivered by its GitHub deadline.\n\n"
            f"Reason: {message}\n\n"
            f"Workflow date: {today_iso()}\n"
            "The publication was not sent because validation failed or the handoff was missing."
        ),
        "html": (
            "<p>The Peer Group Digest was <strong>not delivered</strong> by its GitHub deadline.</p>"
            f"<p>Reason: {html.escape(message)}</p>"
            f"<p>Workflow date: {today_iso()}</p>"
            "<p>The publication was not sent because validation failed or the handoff was missing.</p>"
        ),
    }
    out = request(
        "POST", "/emails", body,
        headers={"Idempotency-Key": f"peer-group-alert/{today_iso()}"}
    )
    ledger["alert_email_id"] = out.get("id")
    ledger["status"] = "alerted"

def main() -> None:
    ledger = current_ledger()
    ledger["checked_at"] = datetime.now(TZ).isoformat()

    if ledger.get("status") == "sent":
        print("Already recorded sent for today; exiting.")
        return

    try:
        if not HANDOFF.exists():
            raise ValidationError("data/handoffs/peer_group.json is missing")
        p = json.loads(HANDOFF.read_text(encoding="utf-8"))
        body_hash = validate_handoff(p)
        ledger["handoff_valid"] = True
        ledger["body_sha256"] = body_hash

        # Ledger and provider duplicate protection.
        exact = [b for b in list_broadcasts() if b.get("name") == p["name"]]
        for b in exact:
            if b.get("status") in {"sent", "queued", "scheduled"}:
                bid = b.get("id")
                ledger["broadcast_id"] = bid
                if b.get("status") != "sent":
                    poll_sent(bid)
                ledger["status"] = "sent"
                ledger["error"] = None
                save_ledger(ledger)
                print(f"Existing same-date broadcast verified: {bid}")
                return

        created = request("POST", "/broadcasts", {
            "name": p["name"],
            "segment_id": p["segmentId"],
            "from": p["from"],
            "reply_to": p["replyTo"],
            "subject": p["subject"],
            "preview_text": p.get("previewText",""),
            "html": p["html"],
            "text": p["text"],
            "send": True,
        })
        bid = created.get("id")
        if not bid:
            raise RuntimeError(f"broadcast create-and-send returned no id: {created}")
        ledger["broadcast_id"] = bid
        poll_sent(bid)
        ledger["status"] = "sent"
        ledger["error"] = None
        save_ledger(ledger)
        print(f"SENT_OK {bid}")

    except Exception as exc:
        ledger["error"] = str(exc)
        try:
            alert(str(exc), ledger)
        except Exception as alert_exc:
            ledger["status"] = "failed"
            ledger["error"] = f"{exc}; alert also failed: {alert_exc}"
        save_ledger(ledger)
        print(f"ERROR: {ledger['error']}", file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
