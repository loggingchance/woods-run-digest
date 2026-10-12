import json,hashlib,os,time
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import correct_daily_digest_x_20261012 as common
import post_to_buffer as adapter
import buffer_queue as b
ROOT=Path(__file__).resolve().parents[1]
REQUEST=ROOT/'data/corrections/striking-2026-10-12-request.json'
RECEIPT=ROOT/'data/corrections/striking-2026-10-12-receipt.json'
common.RECEIPT=RECEIPT
KNOWN={'6acca251712ba82086b3e38c','6accd289355aa519678a0307','6accd404355aa519678a78fd'}
CHANNEL='6843193ed6d25b49a145ff6e'
DATE='2026-10-12'
def candidates(posts):
 return [p for p in posts if p['id'] not in KNOWN and any((p.get(k) or '').startswith(DATE) for k in ('createdAt','dueAt'))]
def main():
 r=json.loads(REQUEST.read_text());assert r['activation']=='PUBLISH_ONE_NON_MART_STRIKING_20261012'
 assert os.environ.get('GITHUB_ACTIONS')=='true'
 assert datetime.now(ZoneInfo('America/Denver')).date().isoformat()==DATE
 org,channels=b.get_channels();c=next(c for c in channels if c['id']==CHANNEL)
 assert c['name']=='ForestBizSchool' and c['service']=='twitter'
 assert not any(c.get(k) for k in ['isDisconnected','isLocked','isQueuePaused'])
 posts=b.recent(org,CHANNEL);others=candidates(posts)
 rec=json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {}
 if others:
  assert len(others)==1,'Ambiguous other posts; no submission'
  post=others[0]
  if post['text']!=r['text']:
   print('EXISTING_OTHER_POST_NO_SUBMISSION '+json.dumps(post));return
  assert r['image_url'] in [a.get('source') for a in post.get('assets',[])], 'Existing image differs'
 else:
  assert not rec.get('attempt_started_at'),'Previous attempt unresolved; no resubmission'
  image=common.fetch_public(r['image_url']);assert hashlib.sha256(image).hexdigest()==r['image_sha256']
  page=common.fetch_public(common.PAGE).decode();assert '121 million board feet' in page and '29.8 million' in page and '46 million board feet' in page
  assert len(r['text'])<=280 and 'Mart' not in r['text'] and common.PAGE in r['text']
  payload={'channelId':CHANNEL,'text':r['text'],'mode':'shareNow','schedulingType':'automatic','source':'woods-run-striking-blm-20261012','assets':[{'image':{'url':r['image_url']}}],'saveToDraft':False,'needsApproval':False}
  rec={'attempt_started_at':datetime.now(timezone.utc).isoformat(),'state':'attempt_started','history_count':len(posts),'payload':payload,'authorization':r['authorization'],'source':r['source'],'image_sha256':r['image_sha256']}
  common.persist(rec)
  response=adapter.graphql('mutation Post($input:CreatePostInput!){createPost(input:$input){... on PostActionSuccess{post{'+b.POST_FIELDS+'}} ... on MutationError{message}}}',{'input':payload})['createPost']
  if response.get('message'):
   rec.update(state='rejected',provider_error=response['message']);common.persist(rec);raise ValueError(response['message'])
  post=response.get('post');assert post and post.get('id'),'No post receipt; reconcile before retry'
  rec.update(state='accepted',replacement=post);common.persist(rec)
 for _ in range(24):
  post=common.fetch_post(post['id']);assert post['channelId']==CHANNEL and post['text']==r['text']
  assert post['status']!='error',json.dumps(post)
  if post['status']=='sent' and post.get('externalLink'):
   assert r['image_url'] in [a.get('source') for a in post['assets']]
   rec.update(state='sent',replacement=post,verified_at=datetime.now(timezone.utc).isoformat());common.persist(rec);print('STRIKING_SENT '+json.dumps(rec));return
  time.sleep(10)
 raise ValueError('Accepted but not yet confirmed sent; do not resubmit')
if __name__=='__main__':main()
