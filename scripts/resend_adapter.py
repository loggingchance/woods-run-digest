#!/usr/bin/env python3
"""Idempotent Resend adapter for the single Woods Run publisher.

This module is intentionally not enabled by the staging workflow. In live mode it:
- recognizes only the exact same-date Woods Run broadcast;
- never clones/reuses a prior date;
- validates same-date subject/body/canonical URL before sending;
- verifies delivery with Resend's Email Metrics API filtered by broadcast_id.
"""
from __future__ import annotations
import html as html_lib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date as date_cls, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
API="https://api.resend.com"
SITE="https://woodsrun.forestenterprise.org"
SEGMENT=os.environ.get("WOODS_RUN_SEGMENT_ID","ec27b7e4-84e2-47af-83ce-7d77732ed557").strip()
FROM="Steve Bick | Woods Run Digest <no_reply@forestenterprise.org>"
REPLY_TO="steve@northeastforests.com"

def fail(msg):
    raise RuntimeError(msg)

def api(method,path,body=None):
    key=os.environ.get("RESEND_API_KEY","").strip()
    if not key:
        fail("RESEND_API_KEY is not configured")
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(API+path,data=data,method=method,headers={
        "Authorization":f"Bearer {key}","Content-Type":"application/json","User-Agent":"WoodsRunNext/1.0"
    })
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        fail(f"Resend HTTP {e.code}: {e.read().decode(errors='replace')}")

def issue_for(date_string):
    issues=json.loads((ROOT/"data/issues.json").read_text(encoding="utf-8"))
    for i in issues:
        if i.get("date")==date_string:
            return i
    fail(f"No issue metadata for {date_string}")

def page_for(issue):
    y,m,d=issue["date"].split("-")
    p=ROOT/y/m/d/"index.html"
    if not p.exists():
        fail(f"Missing canonical page: {p}")
    page=p.read_text(encoding="utf-8")
    canonical=SITE+issue["url"]
    if issue["displayDate"] not in page or canonical not in page:
        fail("Canonical page/date/URL validation failed")
    return page

def strip_html(page):
    text=re.sub(r"<script[\s\S]*?</script>","",page,flags=re.I)
    text=re.sub(r"<style[\s\S]*?</style>","",text,flags=re.I)
    text=re.sub(r"<[^>]+>","\n",text)
    text=html_lib.unescape(text)
    return re.sub(r"\n{3,}","\n\n",text).strip()

def email_html(issue,page):
    main=page.split("<main>",1)[1].split("</main>",1)[0] if "<main>" in page else page
    main=re.sub(r"<header[\s\S]*?</header>","",main,flags=re.I)
    main=main.replace('href="/','href="'+SITE+'/')
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta http-equiv="X-UA-Compatible" content="IE=edge"></head><body style="margin:0;background-color:#f2eee5;"><table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f2eee5"><tr><td align="center"><table width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#fffdf8" style="width:100%;max-width:600px;"><tr><td style="padding-top:28px;padding-right:30px;padding-bottom:28px;padding-left:30px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:23px;color:#333333;"><p style="font-family:Georgia,'Times New Roman',serif;font-size:28px;line-height:34px;color:#1f3b2b;font-weight:bold;">WOODS RUN DIGEST</p><p style="font-family:Georgia,'Times New Roman',serif;font-size:25px;line-height:31px;color:#222222;">{html_lib.escape(issue['displayDate'])}</p>{main}<p style="font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:18px;color:#777777;"><a href="{{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}" style="color:#777777;">Unsubscribe</a></p></td></tr></table></td></tr></table></body></html>"""

def exact_broadcast(subject):
    data=api("GET","/broadcasts")
    rows=data.get("data",data if isinstance(data,list) else [])
    exact=[b for b in rows if b.get("name")==subject]
    if len(exact)>1:
        fail("Multiple exact same-date broadcasts exist; refusing ambiguous send")
    return exact[0] if exact else None

def metrics(broadcast_id,date_string):
    start=date_cls.fromisoformat(date_string)
    end=start+timedelta(days=1)
    q=urllib.parse.urlencode({
        "start_date":start.isoformat(),
        "end_date":end.isoformat(),
        "timezone":"America/Denver",
        "metrics":"sent,delivered,failed,bounced,suppressed",
        "broadcast_id":broadcast_id
    })
    return api("GET","/emails/metrics?"+q).get("totals",{})

def publish(date_string):
    issue=issue_for(date_string)
    page=page_for(issue)
    subject=f"Woods Run Digest — {issue['displayDate']}"
    canonical=SITE+issue["url"]
    b=exact_broadcast(subject)
    if b:
        bid=b["id"]
        detail=api("GET",f"/broadcasts/{bid}")
        if detail.get("subject")!=subject:
            fail("Same-date broadcast subject validation failed")
        body=(detail.get("html") or "")+"\n"+(detail.get("text") or "")
        if issue["displayDate"] not in body or canonical not in body:
            fail("Same-date broadcast body validation failed")
        status=detail.get("status") or b.get("status")
    else:
        html=email_html(issue,page)
        text=strip_html(page)+f"\n\nRead today's edition: {canonical}"
        created=api("POST","/broadcasts",{
            "name":subject,"segment_id":SEGMENT,"from":FROM,"reply_to":[REPLY_TO],
            "subject":subject,"preview_text":issue.get("socialText") or issue["summary"],
            "html":html,"text":text
        })
        bid=created.get("id")
        if not bid:
            fail("Resend broadcast creation returned no ID")
        status="draft"
    if status!="sent":
        api("POST",f"/broadcasts/{bid}/send",{})
    totals={}
    for _ in range(6):
        totals=metrics(bid,date_string)
        if int(totals.get("delivered",0))>=1 and int(totals.get("failed",0))==0:
            break
        time.sleep(10)
    delivered=int(totals.get("delivered",0))
    failed=int(totals.get("failed",0))
    if delivered<1 or failed!=0:
        fail(f"Broadcast delivery not verified: {totals}")
    return {"broadcast_id":bid,"status":"delivered","delivered":delivered,"failed":failed,"metrics":totals}

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: resend_adapter.py YYYY-MM-DD")
    print(json.dumps(publish(sys.argv[1]),ensure_ascii=False))
