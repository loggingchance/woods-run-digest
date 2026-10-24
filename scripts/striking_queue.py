#!/usr/bin/env python3
"""Schedule one distinct daily Woods Run striking observation in native Buffer.

GitHub is a push-only handoff. Buffer owns the 10:00 America/Denver clock.
No Resend, Gmail, or legacy shareNow calls. A durable attempt marker is
committed before any provider mutation; ambiguous attempts are never retried.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, time as clock, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import buffer_queue as buffer
import post_to_buffer as adapter

ROOT = Path(__file__).resolve().parents[1]
DENVER = ZoneInfo('America/Denver')
CHANNEL_ID = '6843193ed6d25b49a145ff6e'
BLOCKING = {'sent', 'scheduled', 'sending', 'processing', 'pending', 'buffer'}


def require(value, message):
    if not value:
        raise ValueError(message)


def receipt_path(date):
    return ROOT / 'data' / 'striking-delivery' / (date + '.json')


def persist(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for command in (
        ['git', 'config', 'user.name', 'github-actions[bot]'],
        ['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'],
        ['git', 'add', str(path.relative_to(ROOT))],
    ):
        subprocess.run(command, cwd=ROOT, check=True)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode != 0
    if changed:
        subprocess.run(['git', 'commit', '-m', 'Record single Woods Run striking provider attempt'], cwd=ROOT, check=True)
        subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=ROOT, check=True)
        subprocess.run(['git', 'rebase', 'origin/main'], cwd=ROOT, check=True)
        subprocess.run(['git', 'push', 'origin', 'HEAD:main'], cwd=ROOT, check=True)


def load_request():
    r = json.loads((ROOT/'data/striking-trigger.json').read_text(encoding='utf-8'))
    date = datetime.now(DENVER).date().isoformat()
    require(r.get('action') == 'schedule_striking' and r.get('date') == date,
            'No approved current-day native striking request')
    due = buffer.parse_time(r['due_at'])
    expected = datetime.combine(datetime.fromisoformat(date).date(), clock(10, 0), DENVER).astimezone(timezone.utc)
    recovery = (date == '2026-10-19' and r.get('recovery_approval') == 'Sentinel_f7f1e1af7a24819185d763cc49817489'
                and due == buffer.parse_time('2026-10-19T22:09:00Z'))
    recovery = recovery or (date == '2026-10-21' and
                r.get('recovery_approval') == 'user-2026-10-21T21:57Z' and
                due.astimezone(DENVER).date().isoformat() == date and due > expected)
    require(due == expected or recovery, 'Striking post must be scheduled for 10:00 America/Denver')
    issue = next((i for i in json.loads((ROOT/'data/issues.json').read_text()) if i['date'] == date), None)
    require(issue and issue.get('strikingText'), 'Current canonical striking observation missing')
    text = issue['strikingText'].strip()
    require(0 < len(text) <= 280, f'Authored strikingText length {len(text)} exceeds Buffer X maximum of 280 characters')
    return r, issue, text, due


def history(text):
    org, channels = buffer.get_channels()
    matched = [c for c in channels if c['id'] == CHANNEL_ID and c.get('name') == 'ForestBizSchool' and c.get('service') == 'twitter']
    require(len(matched) == 1, 'X ForestBizSchool identity missing or ambiguous')
    require(not any(matched[0].get(k) for k in ('isDisconnected', 'isLocked', 'isQueuePaused')),
            'Target X channel is unavailable or paused')
    posts = buffer.recent(org, CHANNEL_ID)
    found = [p for p in posts if (p.get('text') or '').strip() == text]
    require(len(found) <= 1, 'Multiple exact striking posts; do not create another')
    return posts, found[0] if found else None


def schedule():
    request, issue, text, due = load_request()
    path = receipt_path(request['date'])
    record = json.loads(path.read_text()) if path.exists() else None
    if record:
        require(record.get('text') == text and record.get('due_at') == buffer.iso(due),
                'An earlier striking attempt targets different content or time')
    posts, found = history(text)
    if found:
        require(found.get('status') in BLOCKING, 'Existing striking post is in an unverified failure state')
        if not record:
            record = {'date':request['date'],'text':text,'due_at':buffer.iso(due),
                      'state':'existing','post_id':found['id']}
        record.update(provider_status=found['status'], post_id=found['id'],
                      provider_due_at=found.get('dueAt'), external_url=found.get('externalLink'),
                      verified_at=buffer.iso(buffer.now()))
        persist(path, record)
        print('STRIKING_EXISTING '+json.dumps(record, ensure_ascii=False), flush=True)
        return
    require(not record, 'An earlier striking provider attempt is unresolved; never automatically resubmit')
    require(due > buffer.now()+timedelta(seconds=90), 'Striking schedule deadline missed; never post immediately')
    require(adapter.fetch_public(adapter.SITE_ROOT + issue['url'])[0] == 200,
            'Canonical dated issue not publicly reachable')
    record = {'date':request['date'],'text':text,'due_at':buffer.iso(due),
              'channel_id':CHANNEL_ID,'state':'attempt_started',
              'attempt_started_at':buffer.iso(buffer.now()),
              'post_id':None,'history_checked':len(posts),'source':'native-daily-striking',
              'email_attempted':False}
    persist(path, record)
    payload = {'channelId':CHANNEL_ID, 'text':text, 'assets':[],
               'mode':'customScheduled', 'schedulingType':'automatic',
               'dueAt':buffer.iso(due), 'source':'woods-run-striking-daily',
               'saveToDraft':False, 'needsApproval':False}
    query = ('mutation Schedule($input: CreatePostInput!) { createPost(input: $input) { '
             '... on PostActionSuccess { post { '+buffer.POST_FIELDS+' } } '
             '... on MutationError { message } } }')
    result = buffer.gql(query, {'input':payload}).get('createPost', {})
    require(not result.get('message'), 'Buffer rejected native striking schedule: '+str(result.get('message')))
    post = result.get('post')
    require(post and post.get('id'), 'Buffer mutation outcome unknown; do not retry')
    record.update(post_id=post['id'], provider_status=post.get('status'),
                  provider_due_at=post.get('dueAt'), external_url=post.get('externalLink'),
                  state='accepted', accepted_at=buffer.iso(buffer.now()))
    record['schedule_verified'] = bool(post.get('dueAt') and
        abs((buffer.parse_time(post['dueAt'])-due).total_seconds()) <= 2 and post.get('status') in BLOCKING)
    persist(path, record)
    print('STRIKING_SCHEDULE_RESULT '+json.dumps(record, ensure_ascii=False), flush=True)
    require(record['schedule_verified'], 'Buffer has not verified the exact 10 AM scheduled time')


def verify():
    request, issue, text, due = load_request()
    path = receipt_path(request['date'])
    require(path.exists(), 'No striking provider receipt')
    record = json.loads(path.read_text())
    require(record.get('post_id'), 'Striking provider ID is absent')
    if due.timestamp()+95-time.time() >= 1500:
        # Morning preparation queues well ahead of delivery. The daily cron
        # performs the post-due check; do not occupy a runner for hours.
        posts, found = history(text)
        require(found and found.get('id') == record['post_id'] and
                found.get('status') in BLOCKING and found.get('dueAt') and
                abs((buffer.parse_time(found['dueAt'])-due).total_seconds()) <= 2,
                'Advance striking schedule no longer verified')
        print('STRIKING_SCHEDULE_VERIFIED; publication pending scheduled time', flush=True)
        return
    delay = due.timestamp()+95-time.time()
    if delay > 0:
        require(delay < 1500, 'Post-delivery verification wait exceeds bound')
        time.sleep(delay)
    posts, found = history(text)
    require(found and found.get('id') == record['post_id'], 'Buffer returned a different striking post')
    record.update(verified_at=buffer.iso(buffer.now()),provider_status=found.get('status'),
                  external_url=found.get('externalLink'),
                  state='sent' if found.get('status') == 'sent' and found.get('externalLink') else 'unverified')
    persist(path, record)
    print('STRIKING_FINAL_PROVIDER '+json.dumps(record, ensure_ascii=False),flush=True)
    require(record['state'] == 'sent', 'Striking publication not confirmed by provider; no resubmission')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--verify',action='store_true')
    a=p.parse_args()
    if a.verify:verify()
    else:schedule()


if __name__ == '__main__':
    try:main()
    except Exception as exc:
        print('STRIKING_ERROR '+str(exc),file=sys.stderr)
        raise SystemExit(1)

