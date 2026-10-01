#!/usr/bin/env python3
"""Verified, idempotent Buffer delivery adapter for Woods Run."""
from __future__ import annotations
import json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUFFER="https://api.buffer.com"
SITE="https://woodsrun.forestenterprise.org"
RAW="https://raw.githubusercontent.com/loggingchance/woods-run-digest/main"
TARGETS=(
    ("twitter","ForestBizSchool","x"),
    ("instagram","northeastforests","instagram"),
    ("youtube","Steve07870","youtube"),
)

def fail(msg): raise RuntimeError(msg)

def gql(query,variables=None):
    key=os.environ.get("BUFFER_API_KEY","").strip()
    if not key: fail("BUFFER_API_KEY is not configured")
    req=urllib.request.Request(BUFFER,data=json.dumps({"query":query,"variables":variables or {}}).encode(),method="POST",headers={
        "Content-Type":"application/json","Authorization":f"Bearer {key}","User-Agent":"WoodsRunNext/1.0"
    })
    try:
        with urllib.request.urlopen(req,timeout=30) as r: result=json.loads(r.read().decode())
    except urllib.error.HTTPError as e: fail(f"Buffer HTTP {e.code}: {e.read().decode(errors='replace')}")
    if result.get("errors"): fail("Buffer GraphQL error: "+json.dumps(result["errors"]))
    return result.get("data",{})

def issue_for(date_string):
    rows=json.loads((ROOT/"data/issues.json").read_text(encoding="utf-8"))
    for i in rows:
        if i.get("date")==date_string: return i
    fail(f"No issue metadata for {date_string}")

def organization():
    rows=gql("query { account { organizations { id name } } }").get("account",{}).get("organizations",[])
    if len(rows)!=1: fail(f"Expected one Buffer organization, found {len(rows)}")
    return rows[0]["id"]

def channels(org):
    q="""query C($organizationId: OrganizationId!) { channels(input:{organizationId:$organizationId}) { id name service } }"""
    return gql(q,{"organizationId":org}).get("channels",[])

def choose(rows,service,name):
    exact=[x for x in rows if x.get("service")==service and (x.get("name") or "").casefold()==name.casefold()]
    if len(exact)!=1: fail(f"Could not uniquely resolve Buffer {service} channel {name}")
    return exact[0]

def recent(org,channel_id):
    q="""query P($organizationId: OrganizationId!, $channelId: ChannelId!) {
      posts(first:50,input:{organizationId:$organizationId,filter:{status:[sent,scheduled,error],channelIds:[$channelId]},sort:[{field:createdAt,direction:desc}]}) {
        edges { node { id text status createdAt channelId externalLink assets { source mimeType } } }
      }
    }"""
    return [e.get("node",{}) for e in gql(q,{"organizationId":org,"channelId":channel_id}).get("posts",{}).get("edges",[])]

def match_post(posts,service,page_url,asset_name):
    for p in posts:
        text=p.get("text") or ""
        sources=[(a.get("source") or "") for a in (p.get("assets") or [])]
        if service=="twitter" and page_url in text: return p
        if service in ("instagram","youtube") and (page_url in text or any(s.endswith("/"+asset_name) for s in sources)): return p
    return None

def shorten(text,n):
    text=" ".join(text.split())
    if len(text)<=n: return text
    return text[:n-1].rsplit(" ",1)[0].rstrip(" ,;:-")+"…"

def compose(issue,service,page_url):
    if service=="twitter":
        teaser=(issue.get("socialText") or issue["summary"]).strip()
        teaser=shorten(teaser,280-len(page_url)-2)
        return teaser+"\n\n"+page_url
    if service=="instagram":
        return f"Woods Run Digest — {issue['displayDate']}\n\nDaily forestry & forest-products intelligence from The Forest Business School.\n\nRead today’s edition: link in bio.\nwoodsrun.forestenterprise.org"
    return f"Woods Run Digest — {issue['displayDate']}\n\n{issue['summary']}\n\nRead the full edition: {page_url}\n\nDaily forestry & forest-products intelligence from The Forest Business School."

def youtube_title(issue):
    return shorten(issue.get("cardTeaser") or issue.get("socialText") or issue["summary"],100)

def create_post(channel_id,service,text,asset_url,issue):
    q="""mutation M($input: CreatePostInput!) {
      createPost(input:$input) {
        ... on PostActionSuccess { post { id text status dueAt externalLink assets { source mimeType } } }
        ... on MutationError { message }
      }
    }"""
    if service=="twitter":
        assets=[{"image":{"url":asset_url}}]; metadata=None
    elif service=="instagram":
        assets=[{"video":{"url":asset_url,"metadata":{"thumbnailOffset":1500}}}]
        metadata={"instagram":{"type":"reel","shouldShareToFeed":True}}
    else:
        assets=[{"video":{"url":asset_url}}]
        metadata={"youtube":{"title":youtube_title(issue),"categoryId":"27","privacy":"public","madeForKids":False,"notifySubscribers":True,"embeddable":True,"license":"youtube"}}
    inp={"text":text,"channelId":channel_id,"schedulingType":"automatic","mode":"shareNow","source":"woods-run-digest-next","assets":assets}
    if metadata: inp["metadata"]=metadata
    payload=gql(q,{"input":inp}).get("createPost") or {}
    if payload.get("message"): fail(f"Buffer rejected {service}: {payload['message']}")
    p=payload.get("post")
    if not p: fail(f"Unexpected Buffer response for {service}: {payload}")
    return p

def wait_sent(org,channel_id,post_id,service):
    last=None
    for _ in range(12):
        rows=recent(org,channel_id)
        last=next((p for p in rows if p.get("id")==post_id),None)
        if last:
            status=last.get("status")
            if status=="error": fail(f"Buffer {service} post entered error state: {post_id}")
            if status=="sent" and last.get("externalLink"): return last
        time.sleep(10)
    fail(f"Buffer {service} publication not verified sent with external link: {last or post_id}")

def publish(date_string):
    issue=issue_for(date_string)
    page_url=SITE+issue["url"]
    card_name=date_string+".png"; reel_name=date_string+".mp4"
    card=ROOT/"assets/cards"/card_name; reel=ROOT/"assets/videos"/reel_name
    if not card.exists() or not reel.exists(): fail("Dated social assets are missing")
    org=organization(); rows=channels(org); out={}
    for service,name,key in TARGETS:
        ch=choose(rows,service,name)
        asset_name=card_name if service=="twitter" else reel_name
        existing=match_post(recent(org,ch["id"]),service,page_url,asset_name)
        if existing:
            if existing.get("status")=="error": fail(f"Existing same-date {service} post is error")
            if existing.get("status")=="sent" and existing.get("externalLink"):
                out[key]={"status":"sent","post_id":existing["id"],"external_url":existing["externalLink"]}
                continue
            existing=wait_sent(org,ch["id"],existing["id"],service)
            out[key]={"status":"sent","post_id":existing["id"],"external_url":existing["externalLink"]}
            continue
        asset_url=f"{RAW}/assets/cards/{card_name}" if service=="twitter" else f"{RAW}/assets/videos/{reel_name}"
        created=create_post(ch["id"],service,compose(issue,service,page_url),asset_url,issue)
        sent=wait_sent(org,ch["id"],created["id"],service)
        out[key]={"status":"sent","post_id":sent["id"],"external_url":sent["externalLink"]}
    return out

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: buffer_adapter.py YYYY-MM-DD")
    print(json.dumps(publish(sys.argv[1]),ensure_ascii=False))
