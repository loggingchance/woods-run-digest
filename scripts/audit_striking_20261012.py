import json,sys
from datetime import datetime,timezone
sys.path.insert(0,'scripts')
import buffer_queue as b
org,channels=b.get_channels()
c=next(c for c in channels if c['id']=='6843193ed6d25b49a145ff6e')
assert c['name']=='ForestBizSchool' and c['service']=='twitter'
posts=b.recent(org,c['id'])
report={'checked_at':datetime.now(timezone.utc).isoformat(),'count':len(posts),'channel':c,'recent':posts[:50]}
open('data/corrections/striking-2026-10-12-audit.json','w').write(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
