#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, time, urllib.request, urllib.error
from pathlib import Path

API="https://api.resend.com"
KEY=os.environ["RESEND_API_KEY"]
TO="steve@northeastforests.com"
FROM="Woods Run Test <no_reply@forestenterprise.org>"
ROOT=Path(__file__).resolve().parents[1]
DATE="2026-10-02"
SUBJECT="TEST — Woods Run Digest — October 2, 2026"

def req(method,path,body=None,headers=None):
    data=None if body is None else json.dumps(body).encode()
    h={"Authorization":f"Bearer {KEY}","Content-Type":"application/json","User-Agent":"WoodsRunTest/1.0"}
    if headers: h.update(headers)
    r=urllib.request.Request(API+path,data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(r,timeout=45) as x:
            raw=x.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail=e.read().decode(errors='replace')
        if e.code == 404 and method == "GET" and path.startswith("/emails/"):
            return {"_transient_not_found": True}
        raise RuntimeError(f"Resend HTTP {e.code}: {detail}")

def main():
    y,m,d=DATE.split("-")
    page=(ROOT/y/m/d/"index.html").read_text(encoding="utf-8")
    if "October 2, 2026" not in page:
        raise SystemExit("wrong canonical issue")
    body=page.split("<main>",1)[1].split("</main>",1)[0] if "<main>" in page else page
    body=body.replace('href="/','href="https://woodsrun.forestenterprise.org/')
    html=f'''<!DOCTYPE html><html><body><p><strong>This is the scheduled GitHub/Resend delivery test requested after the automation rebuild.</strong></p>{body}</body></html>'''
    text=re.sub(r"<[^>]+>","\n",body)
    payload={"from":FROM,"to":[TO],"reply_to":[TO],"subject":SUBJECT,"html":html,"text":"SCHEDULED DELIVERY TEST\n\n"+text}
    out=req("POST","/emails",payload,{"Idempotency-Key":"woods-run-scheduled-test/2026-10-02-v2"})
    eid=out.get("id")
    if not eid: raise SystemExit(f"no email id: {out}")
    deadline=time.time()+180
    last="unknown"
    while time.time()<deadline:
        detail=req("GET",f"/emails/{eid}")
        if detail.get("_transient_not_found"):
            time.sleep(5)
            continue
        last=detail.get("last_event") or "unknown"
        if last=="delivered":
            print("TEST_DELIVERED",eid)
            return
        if last in {"bounced","failed","suppressed","complained"}:
            raise SystemExit(f"test email ended {last}")
        time.sleep(5)
    raise SystemExit(f"test email not delivered in 180s; last={last}")

if __name__=="__main__":
    main()
