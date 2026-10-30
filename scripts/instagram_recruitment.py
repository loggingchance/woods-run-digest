#!/usr/bin/env python3
"""Isolated Instagram recruitment handoff; Buffer owns all delivery timing."""
import hashlib, json, re, subprocess, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import buffer_queue as b
ROOT=Path(__file__).resolve().parents[1]
CHANNEL='6844cc71d6d25b49a1de682e'
PREFIX='assets/instagram-recruitment/'
RAW='https://raw.githubusercontent.com/loggingchance/woods-run-digest/main/'
DENVER=ZoneInfo('America/Denver')

def check_item(item):
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:-launch)?',item['slot']), 'Invalid slot'
    assert item['asset'].startswith(PREFIX) and '..' not in item['asset'] and item['asset'].endswith('.jpg'), 'Invalid asset path'
    assert re.fullmatch('[a-f0-9]{64}',item['sha256']), 'Invalid asset digest'
    text=item['caption']
    assert 'The Woods Run Digest' in text and 'link in bio' in text.lower() and 20<len(text)<2200, 'Invalid caption'
    if item.get('immediate'):
        assert item['slot']=='2026-10-30-launch' and datetime.now(DENVER).date().isoformat()=='2026-10-30', 'Immediate exception expired'
        due=None
    else:
        due=datetime.fromisoformat(item['slot']).replace(hour=8,tzinfo=DENVER)
        assert due.weekday() in (1,3), 'Not a Tuesday/Thursday slot'
    return due

def checkpoint(path,record):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
    subprocess.run(['git','add',str(path.relative_to(ROOT))],cwd=ROOT,check=True)
    changed=subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode
    if changed:
        subprocess.run(['git','commit','-m','Record Instagram recruitment handoff receipt'],cwd=ROOT,check=True)
        subprocess.run(['git','pull','--rebase','origin','main'],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','HEAD:main'],cwd=ROOT,check=True)

def run():
    request=json.loads((ROOT/'data/instagram-recruitment-trigger.json').read_text())
    assert request['action'] in ('audit','publish','verify')
    items=request['items']; assert 1<=len(items)<=6
    assert len({i['slot'] for i in items})==len(items)
    org,channels=b.get_channels()
    ch=[c for c in channels if c['id']==CHANNEL]
    assert len(ch)==1 and ch[0]['service']=='instagram' and ch[0]['name']=='northeastforests'
    assert ch[0]['timezone']=='America/Denver'
    assert not any(ch[0][k] for k in ('isDisconnected','isLocked','isQueuePaused'))
    print('CAMPAIGN_CHANNEL '+json.dumps(ch[0]))
    for item in items:
        due=check_item(item)
        path=ROOT/'data/instagram-recruitment-receipts'/(item['slot']+'.json')
        record=json.loads(path.read_text()) if path.exists() else {'slot':item['slot'],'request':item}
        assert record['request']==item, 'Slot already bound to different approved content'
        posts=b.recent(org,CHANNEL)
        found=[p for p in posts if p['id']==record.get('post_id') or p.get('text','').strip()==item['caption'].strip() or any(a.get('source')==RAW+item['asset'] for a in p.get('assets',[]))]
        assert len(found)<=1,'Multiple matching posts; refusing duplicates'
        # Prevent any campaign receipt from using the same artwork for another slot.
        for other in (ROOT/'data/instagram-recruitment-receipts').glob('*.json'):
            if other!=path:
                prior=json.loads(other.read_text())['request']
                assert prior['asset']!=item['asset'] and prior['sha256']!=item['sha256'], 'Campaign artwork already used'
        record['duplicate_search']={'complete':True,'posts_checked':len(posts)}
        record['checked_at']=datetime.now(timezone.utc).isoformat()
        if not found and request['action']=='publish':
            assert not record.get('attempt_started_at'),'Unresolved earlier attempt: manual reconciliation required'
            assert due is None or due>datetime.now(DENVER),'Missed slot; no late immediate fallback'
            data=(ROOT/item['asset']).read_bytes()
            assert data[:2]==b'\xff\xd8' and len(data)<8_000_000 and hashlib.sha256(data).hexdigest()==item['sha256']
            with urllib.request.urlopen(RAW+item['asset'],timeout=30) as response:
                assert response.status==200 and hashlib.sha256(response.read()).hexdigest()==item['sha256'],'Public asset mismatch'
            payload={'channelId':CHANNEL,'text':item['caption'],'assets':[{'image':{'url':RAW+item['asset']}}], 'metadata':{'instagram':{'type':'post','shouldShareToFeed':True}},'schedulingType':'automatic','mode':'shareNow' if due is None else 'customScheduled','source':'woods-run-instagram-recruitment','saveToDraft':False,'needsApproval':False}
            if due: payload['dueAt']=due.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
            record['attempt_started_at']=datetime.now(timezone.utc).isoformat()
            checkpoint(path,record) # Durable before the only mutation; ambiguous submissions never retried.
            result=b.gql('mutation Campaign($input:CreatePostInput!){createPost(input:$input){... on PostActionSuccess{post{'+b.POST_FIELDS+'}} ... on MutationError{message}}}',{'input':payload})['createPost']
            if result.get('message'): raise RuntimeError(result['message'])
            post=result.get('post'); assert post and post.get('id'),'Missing provider receipt'
            record['post_id']=post['id'];record['provider_post']=post
            checkpoint(path,record)
            found=[post]
        if found:
            record['post_id']=found[0]['id']
            # Fresh provider readback, never treat createPost alone as final delivery.
            fresh=b.recent(org,CHANNEL)
            post=next(p for p in fresh if p['id']==record['post_id'])
            record['provider_post']=post
            assert post['channelId']==CHANNEL and post['text']==item['caption'] and len(post.get('assets',[]))==1
            assert post['assets'][0]['source']==RAW+item['asset'] and post['assets'][0]['mimeType']=='image/jpeg'
            assert post['status'] in b.BLOCKING, 'Provider failed or unknown status'
            if due: assert b.parse_time(post['dueAt'])==due.astimezone(timezone.utc),'Provider schedule mismatch'
            if request['action']!='audit': checkpoint(path,record)
        print('CAMPAIGN_RECEIPT '+json.dumps(record,ensure_ascii=False))
        if request['action']=='verify': assert found,'Missing campaign post'
    # First immediate post is monitored to the provider's terminal sent state.
    if request['action']=='publish':
        for item in items:
            if not item.get('immediate'): continue
            path=ROOT/'data/instagram-recruitment-receipts'/(item['slot']+'.json')
            record=json.loads(path.read_text())
            for attempt in range(40):
                post=next(p for p in b.recent(org,CHANNEL) if p['id']==record['post_id'])
                record['provider_post']=post
                if post['status']=='sent':
                    checkpoint(path,record); print('CAMPAIGN_SENT '+json.dumps(post));break
                assert post['status'] in b.BLOCKING,'Immediate publication failed'
                time.sleep(15)
            else:
                checkpoint(path,record);raise RuntimeError('Immediate publication remains pending; inspect provider before any retry')

if __name__=='__main__': run()
