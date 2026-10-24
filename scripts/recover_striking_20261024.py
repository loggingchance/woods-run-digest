"""One approved October 24 recovery; never retry an ambiguous mutation."""
import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import buffer_queue as b
import striking_queue as s
import post_to_buffer as adapter

DATE = '2026-10-24'
URL = 'https://woodsrun.forestenterprise.org/2026/10/24/'
TEXT = ('Alberta offers C$60M for technology demonstrations, including forestry. '
        'Applicants can be based elsewhere; deployment in Alberta and private matching funds are required. '
        'Expressions of interest deadline: Dec. 16, 5 p.m. Mountain. ' + URL)

def check_text():
    # This exact fixed payload is entirely ASCII with precisely one URL.
    # X counts that URL as 23; every remaining character has weight one.
    assert TEXT.isascii() and TEXT.count('https://') == 1 and TEXT.endswith(URL)
    assert len(TEXT) == 279 and len(TEXT) <= 280
    assert len(TEXT) - len(URL) + 23 == 253
    return TEXT

def history():
    org, channels = b.get_channels()
    target = [c for c in channels if c['id'] == s.CHANNEL_ID and c['name'] == 'ForestBizSchool' and c['service'] == 'twitter']
    assert len(target) == 1 and not any(target[0].get(k) for k in ('isDisconnected','isLocked','isQueuePaused')), 'Unsafe channel'
    return b.recent(org, s.CHANNEL_ID)

def same_story(post):
    text = (post.get('text') or '').lower()
    return text.strip() == TEXT.lower() or ('alberta' in text and '60' in text and
        any(word in text for word in ('forestry', 'demonstration', 'technology', 'challenge')))

def main():
    assert datetime.now(ZoneInfo('America/Denver')).date().isoformat() == DATE, 'Wrong local date'
    assert os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'No reruns; reconcile independently'
    check_text()
    path = s.receipt_path(DATE)
    record = json.loads(path.read_text())
    phase = sys.argv[1]
    if phase == 'prepare':
        assert record['state'] == 'provider_rejected' and record.get('post_id') is None
        assert record['provider_error'] == 'Invalid post: Twitter / X posts cannot exceed 280 characters.'
        assert record['provider_error_evidence'] == 'GitHub Actions run 40108872619 job 120916190012, 2026-10-24T15:51:37Z'
        assert not record.get('recovery'), 'Recovery already attempted'
        posts = history()
        matches = [p for p in posts if same_story(p)]
        print('ALBERTA_HISTORY_MATCHES ' + json.dumps(matches), flush=True)
        assert not matches, 'Same Alberta story exists; no mutation'
        assert adapter.fetch_public(URL)[0] == 200, 'Issue not public'
        record['recovery'] = dict(state='attempt_started', text=TEXT, post_id=None,
            run_id=os.environ['GITHUB_RUN_ID'], attempt_started_at=b.iso(b.now()),
            history_checked=len(posts), raw_length=len(TEXT), weighted_length=253,
            source='one-time-approved-late-alberta-recovery')
        # Original rejection evidence remains intact. A failed push prevents send.
        s.persist(path, record)
        return
    recovery = record['recovery']
    assert recovery['run_id'] == os.environ['GITHUB_RUN_ID']
    if phase == 'send':
        assert recovery['state'] == 'attempt_started' and recovery['post_id'] is None
        assert not [p for p in history() if same_story(p)], 'Same Alberta story appeared'
        check_text()
        payload = dict(channelId=s.CHANNEL_ID, text=TEXT, assets=[], mode='shareNow',
            schedulingType='automatic', source='woods-run-striking-recovery-20261024',
            saveToDraft=False, needsApproval=False)
        query = 'mutation Recovery($input: CreatePostInput!) { createPost(input: $input) { ... on PostActionSuccess { post { ' + b.POST_FIELDS + ' } } ... on MutationError { message } } }'
        result = b.gql(query, {'input':payload}).get('createPost', {})
        if result.get('message'):
            recovery.update(state='provider_rejected', provider_error=result['message'])
            s.persist(path, record)
            raise ValueError(result['message'])
        post = result.get('post')
        assert post and post.get('id'), 'Unknown mutation outcome; no retry'
        recovery.update(state='accepted',post_id=post['id'],provider_status=post.get('status'),
            external_url=post.get('externalLink'),accepted_at=b.iso(b.now()))
        print('ALBERTA_ACCEPTED ' + json.dumps(recovery), flush=True)
        s.persist(path, record)
        return
    assert phase == 'verify' and recovery.get('post_id')
    for attempt in range(10):
        matches = [p for p in history() if p['id'] == recovery['post_id']]
        assert len(matches) == 1, 'Accepted ID missing; no resubmission'
        post = matches[0]
        recovery.update(provider_status=post.get('status'),external_url=post.get('externalLink'),
            verified_at=b.iso(b.now()))
        if post.get('status') == 'sent' and post.get('externalLink'):
            recovery['state'] = 'sent'
            break
        if post.get('status') in ('failed','error'): break
        time.sleep(30)
    s.persist(path, record)
    print('ALBERTA_FINAL ' + json.dumps(recovery), flush=True)
    assert recovery['state'] == 'sent', 'Sent permalink unconfirmed; no resubmission'

if __name__ == '__main__':
    main()
