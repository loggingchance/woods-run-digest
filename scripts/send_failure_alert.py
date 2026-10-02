#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API = "https://api.resend.com"
API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
TO = "steve@northeastforests.com"
FROM = "Woods Run Monitor <no_reply@forestenterprise.org>"
TZ = ZoneInfo("America/New_York")

def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)

def request(body: dict, key: str) -> dict:
    if not API_KEY:
        fail("RESEND_API_KEY is not configured; cannot send failure alert")
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + "/emails",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Idempotency-Key": key,
            "User-Agent": "WoodsRunMonitor/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8", "replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        fail(f"Resend HTTP {exc.code}: {exc.read().decode(errors='replace')}")

def main() -> None:
    reason = os.environ.get("FAILURE_REASON", "GitHub publisher failed before verified completion.").strip()
    now = datetime.now(TZ)
    display = f"{now.strftime('%b')} {now.day}"
    subject = f"Woods Run — {display} NOT delivered"
    text = (
        "The Woods Run Digest did not reach verified completion by the GitHub publisher deadline.\n\n"
        f"Reason: {reason}\n\n"
        f"Checked: {now.isoformat()}\n"
        "The system withheld completion rather than sending stale or partial content."
    )
    body = {
        "from": FROM,
        "to": [TO],
        "subject": subject,
        "text": text,
        "html": (
            "<p>The Woods Run Digest did <strong>not</strong> reach verified completion by the GitHub publisher deadline.</p>"
            f"<p>Reason: {html.escape(reason)}</p>"
            f"<p>Checked: {html.escape(now.isoformat())}</p>"
            "<p>The system withheld completion rather than sending stale or partial content.</p>"
        ),
    }
    out = request(body, f"woods-run-failure/{now.date().isoformat()}")
    print("ALERT_SENT", out.get("id", out))

if __name__ == "__main__":
    main()
