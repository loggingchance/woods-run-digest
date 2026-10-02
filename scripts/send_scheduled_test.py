#!/usr/bin/env python3
from __future__ import annotations

import html as html_lib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.resend.com"
KEY = os.environ["RESEND_API_KEY"]
TO = "steve@northeastforests.com"
FROM = "Steve Bick | Woods Run Digest <no_reply@forestenterprise.org>"
ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-10-02"
DISPLAY = "October 2, 2026"
SUBJECT = "TEST — Woods Run Digest — October 2, 2026 — FORMATTED SCHEDULE TEST"

def req(method, path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    h = {
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "User-Agent": "WoodsRunFormattedTest/1.0",
    }
    if headers:
        h.update(headers)
    r = urllib.request.Request(API + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=45) as x:
            raw = x.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if e.code == 404 and method == "GET" and path.startswith("/emails/"):
            return {"_transient_not_found": True}
        raise RuntimeError(f"Resend HTTP {e.code}: {detail}")

def text_from_html(value: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", value, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def build_email():
    y, m, d = DATE.split("-")
    page = (ROOT / y / m / d / "index.html").read_text(encoding="utf-8")
    if DISPLAY not in page:
        raise SystemExit("wrong canonical issue")
    body = page.split("<main>",1)[1].split("</main>",1)[0] if "<main>" in page else page
    body = re.sub(r"<header[\s\S]*?</header>", "", body, flags=re.I)
    body = body.replace('href="/', 'href="https://woodsrun.forestenterprise.org/')
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>{SUBJECT}</title>
</head>
<body style="margin:0;background-color:#f2eee5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f2eee5" style="width:100%;background-color:#f2eee5;">
<tr><td align="center" style="padding-top:24px;padding-right:12px;padding-bottom:24px;padding-left:12px;">
<table width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#fffdf8" style="width:100%;max-width:600px;background-color:#fffdf8;border:1px solid #d4c7ad;">
<tr><td bgcolor="#1f3b2b" style="background-color:#1f3b2b;padding-top:22px;padding-right:28px;padding-bottom:18px;padding-left:28px;text-align:center;">
<p style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:28px;line-height:34px;color:#ffffff;font-weight:bold;">WOODS RUN DIGEST</p>
<p style="margin-top:6px;margin-right:0;margin-bottom:0;margin-left:0;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:20px;color:#e9dfc4;">Formatted scheduled-delivery test · {DISPLAY}</p>
</td></tr>
<tr><td style="padding-top:28px;padding-right:30px;padding-bottom:28px;padding-left:30px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:23px;color:#333333;">
<p style="margin-top:0;margin-right:0;margin-bottom:20px;margin-left:0;padding-top:10px;padding-right:12px;padding-bottom:10px;padding-left:12px;background-color:#f3ead7;border-left:4px solid #b28b45;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:21px;color:#333333;">This is a scheduled GitHub → Resend test using the production Woods Run formatting path.</p>
{body}
<p style="margin-top:24px;margin-right:0;margin-bottom:0;margin-left:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:18px;color:#777777;">The Forest Business School · <a href="https://www.forestenterprise.org" style="color:#6e5a2f;">forestenterprise.org</a></p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""
    text = "FORMATTED SCHEDULED DELIVERY TEST\n\n" + text_from_html(body)
    return html, text

def main():
    html, text = build_email()
    payload = {
        "from": FROM,
        "to": [TO],
        "reply_to": [TO],
        "subject": SUBJECT,
        "html": html,
        "text": text,
    }
    out = req("POST", "/emails", payload, {
        "Idempotency-Key": "woods-run-formatted-schedule-test/2026-10-02-v1"
    })
    eid = out.get("id")
    if not eid:
        raise SystemExit(f"no email id: {out}")

    deadline = time.time() + 180
    last = "unknown"
    while time.time() < deadline:
        detail = req("GET", f"/emails/{eid}")
        if detail.get("_transient_not_found"):
            time.sleep(5)
            continue
        last = detail.get("last_event") or "unknown"
        if last == "delivered":
            print("TEST_DELIVERED", eid)
            return
        if last in {"bounced","failed","suppressed","complained"}:
            raise SystemExit(f"test email ended {last}")
        time.sleep(5)
    raise SystemExit(f"test email not delivered in 180s; last={last}")

if __name__ == "__main__":
    main()
