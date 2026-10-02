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
API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
WORKFLOW = os.environ.get("DELIVERY_WORKFLOW", "").strip()
HANDOFF_PATH = os.environ.get("HANDOFF_PATH", "").strip()
TIMEZONE = os.environ.get("DELIVERY_TIMEZONE", "America/Denver").strip()
EXPECTED_FROM = os.environ.get("EXPECTED_FROM", "").strip()
EXPECTED_TO = os.environ.get("EXPECTED_TO", "steve@northeastforests.com").strip()
ALERT_FROM = os.environ.get("ALERT_FROM", "Automation Monitor <no-reply@forestenterprise.org>").strip()
LEDGER_DIR = ROOT / "data/delivery-ledger"

class ValidationError(Exception):
    pass

def now_local() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE))

def request(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict:
    if not API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured")
    data = None if body is None else json.dumps(body).encode("utf-8")
    h = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "DeterministicDelivery/1.0",
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
    safe = re.sub(r"[^a-z0-9-]+", "-", WORKFLOW.lower()).strip("-")
    return LEDGER_DIR / f"{safe}-{date_iso}.json"

def load_ledger(date_iso: str) -> dict:
    p = ledger_path(date_iso)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {
        "workflow": WORKFLOW,
        "date": date_iso,
        "checked_at": None,
        "handoff_valid": False,
        "body_sha256": None,
        "email_id": None,
        "last_event": None,
        "status": "pending",
        "alert_email_id": None,
        "error": None,
    }

def save_ledger(row: dict) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path(row["date"]).write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def previous_sent_hash(date_iso: str) -> str | None:
    if not LEDGER_DIR.exists():
        return None
    rows = []
    for p in LEDGER_DIR.glob("*.json"):
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if row.get("workflow") == WORKFLOW and row.get("date","") < date_iso and row.get("status") == "delivered" and row.get("body_sha256"):
            rows.append(row)
    if not rows:
        return None
    rows.sort(key=lambda x: x["date"], reverse=True)
    return rows[0]["body_sha256"]

def validate_handoff(p: dict, date_iso: str) -> str:
    required = ["workflow","date","displayDate","from","to","replyTo","subject","html","text","send"]
    missing = [k for k in required if k not in p]
    if missing:
        raise ValidationError("missing fields: " + ", ".join(missing))
    if p["workflow"] != WORKFLOW:
        raise ValidationError(f"workflow mismatch: {p['workflow']!r}")
    if p["date"] != date_iso:
        raise ValidationError(f"handoff date is {p['date']!r}; expected {date_iso!r}")
    if EXPECTED_FROM and p["from"] != EXPECTED_FROM:
        raise ValidationError("wrong sender")
    if p["to"] != [EXPECTED_TO]:
        raise ValidationError("wrong recipient")
    if p["replyTo"] != [EXPECTED_TO]:
        raise ValidationError("wrong reply-to")
    if p["send"] is not True:
        raise ValidationError("send flag is not true")
    if p["displayDate"] not in p["subject"]:
        raise ValidationError("subject does not contain current display date")
    if len(p["html"]) < 1200:
        raise ValidationError(f"HTML body too short ({len(p['html'])} chars)")
    if len(p["text"]) < 500:
        raise ValidationError(f"text body too short ({len(p['text'])} chars)")
    combined = p["html"] + "\n" + p["text"]
    low = combined.lower()
    for marker in ("todo", "placeholder", "lorem ipsum"):
        if marker in low:
            raise ValidationError(f"placeholder marker found: {marker}")
    stripped = combined.replace("{{{RESEND_UNSUBSCRIBE_URL}}}", "")
    if "{{" in stripped or "}}" in stripped:
        raise ValidationError("unexpected template marker remains")
    for href in re.findall(r'href=["\']([^"\']+)["\']', p["html"], flags=re.I):
        if href == "{{{RESEND_UNSUBSCRIBE_URL}}}":
            continue
        if not href.startswith("https://"):
            raise ValidationError(f"non-absolute link: {href}")
    digest = hashlib.sha256((p["subject"] + "\n" + p["text"] + "\n" + p["html"]).encode("utf-8")).hexdigest()
    prior = previous_sent_hash(date_iso)
    if prior and digest == prior:
        raise ValidationError("body hash matches previous delivered issue")
    return digest

def poll_delivery(email_id: str, timeout: int = 180) -> str:
    deadline = time.time() + timeout
    last = "unknown"
    while time.time() < deadline:
        detail = request("GET", f"/emails/{email_id}")
        last = detail.get("last_event") or "unknown"
        if last == "delivered":
            return last
        if last in {"bounced", "failed", "suppressed", "complained"}:
            raise RuntimeError(f"email ended in last_event={last}")
        time.sleep(5)
    raise RuntimeError(f"email did not reach delivered within {timeout}s; last_event={last}")

def send_alert(reason: str, row: dict) -> None:
    now = now_local()
    subject = f"{WORKFLOW} — {now.date().isoformat()} NOT delivered"
    payload = {
        "from": ALERT_FROM,
        "to": [EXPECTED_TO],
        "subject": subject,
        "text": (
            f"{WORKFLOW} was not delivered by its deterministic GitHub deadline.\n\n"
            f"Reason: {reason}\n\nChecked: {now.isoformat()}\n"
            "The sender refused stale, duplicate, missing, or partial content."
        ),
        "html": (
            f"<p><strong>{html.escape(WORKFLOW)}</strong> was not delivered by its deterministic GitHub deadline.</p>"
            f"<p>Reason: {html.escape(reason)}</p><p>Checked: {html.escape(now.isoformat())}</p>"
            "<p>The sender refused stale, duplicate, missing, or partial content.</p>"
        ),
    }
    out = request("POST", "/emails", payload, headers={"Idempotency-Key": f"{WORKFLOW}-alert/{now.date().isoformat()}"})
    row["alert_email_id"] = out.get("id")
    row["status"] = "alerted"

def main() -> None:
    if not WORKFLOW or not HANDOFF_PATH:
        raise SystemExit("DELIVERY_WORKFLOW and HANDOFF_PATH are required")
    date_iso = now_local().date().isoformat()
    row = load_ledger(date_iso)
    row["checked_at"] = now_local().isoformat()
    if row.get("status") == "delivered":
        print("Already delivered for today; exiting.")
        return
    handoff = ROOT / HANDOFF_PATH
    try:
        if not handoff.exists():
            raise ValidationError(f"handoff missing: {HANDOFF_PATH}")
        p = json.loads(handoff.read_text(encoding="utf-8"))
        digest = validate_handoff(p, date_iso)
        row["handoff_valid"] = True
        row["body_sha256"] = digest

        payload = {
            "from": p["from"],
            "to": p["to"],
            "reply_to": p["replyTo"],
            "subject": p["subject"],
            "html": p["html"],
            "text": p["text"],
        }
        out = request("POST", "/emails", payload, headers={"Idempotency-Key": f"{WORKFLOW}/{date_iso}"})
        email_id = out.get("id")
        if not email_id:
            raise RuntimeError(f"send returned no email id: {out}")
        row["email_id"] = email_id
        row["last_event"] = poll_delivery(email_id)
        row["status"] = "delivered"
        row["error"] = None
        save_ledger(row)
        print(f"DELIVERED_OK {email_id}")
    except Exception as exc:
        row["error"] = str(exc)
        try:
            send_alert(str(exc), row)
        except Exception as alert_exc:
            row["status"] = "failed"
            row["error"] = f"{exc}; alert also failed: {alert_exc}"
        save_ledger(row)
        print(f"ERROR: {row['error']}", file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
