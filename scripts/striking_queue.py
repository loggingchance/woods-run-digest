#!/usr/bin/env python3
"""Schedule one distinct daily Woods Run striking observation in native Buffer.

GitHub is a push-only handoff. Buffer owns the 10:00 America/Denver clock.
No Resend, Gmail, or legacy shareNow calls. A durable attempt marker is
committed before any provider mutation; ambiguous attempts are never retried.
"""
from __future__ import annotations
import argparse
import json
import hashlib
import subprocess
import sys
import time
from datetime import datetime, time as clock, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import striking_visual
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
    if date >= '2026-11-03' and datetime.fromisoformat(date).weekday() >= 5:
        feature = issue.get('weekendFeature') or {}
        require(issue.get('strikingSkip') is not True and issue.get('weekendFeatureStatus') == 'approved'
                and issue.get('strikingSource') == 'weekend_feature'
                and issue.get('strikingText') == feature.get('striking_text')
                and feature.get('kind') == ('profile' if datetime.fromisoformat(date).weekday() == 5 else 'human_interest'),
                'Weekend striking requires the approved canonical feature')
    # Steve's explicit November 16 Rumford selection, with no URL or image.
    if (date == '2026-11-16' and r.get('owner_approval') == 'phone-c24fc492-eefc-4d00-aa33-53c80c630526'):
        issue = dict(issue, strikingText=r['text_only_override'])
    if (date == '2026-11-23' and r.get('owner_approval') == 'woods-to-wheels-2026-11-23' and
            r.get('text_only_override') == "Six logging crews in a 2015 Auburn study averaged 0.51 gallons of diesel per ton of wood before it ever got on a truck. At $6 a gallon, that’s about $3 a ton in harvesting fuel alone. Source: Woods to Wheels, The Forest Business School."):
        issue = dict(issue, strikingText=r['text_only_override'])
    if (date == '2026-11-23' and r.get('owner_approval') == 'woods-to-wheels-northern-2026-11-23' and
            r.get('text_only_override') == "One New Brunswick hardwood producer used about a U.S. gallon of diesel per green short ton just to get logs to the roadside, before the haul to the mill. That’s about $6 per ton at US$6 a gallon. Source: Woods to Wheels, The Forest Business School."):
        issue = dict(issue, strikingText=r['text_only_override'])
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


def edit_northern_once(path, record, text, due):
    require(record and record.get('date') == '2026-11-23' and
            record.get('channel_id') == CHANNEL_ID and record.get('post_id') == '6b045ac9fb49201520eac5ad' and
            record.get('due_at') == buffer.iso(due) and record.get('schedule_verified') and
            not record.get('visual'), 'Cannot prove the exact approved scheduled post')
    old = "Six logging crews in a 2015 Auburn study averaged 0.51 gallons of diesel per ton of wood before it ever got on a truck. At $6 a gallon, that’s about $3 a ton in harvesting fuel alone. Source: Woods to Wheels, The Forest Business School."
    require(record.get('text') in (old, text), 'Unexpected existing caption; do not edit')
    posts, found = history(text)
    if not found:
        require(record.get('text') == old and not record.get('northern_edit_attempt'), 'Prior edit uncertain; do not retry')
        require(due > buffer.now() + timedelta(seconds=90), 'Too close to publication to edit')
        found = next((p for p in posts if p.get('id') == record['post_id']), None)
        require(found and found.get('text') == old and found.get('status') in ('scheduled', 'buffer') and
                found.get('dueAt') and abs((buffer.parse_time(found['dueAt']) - due).total_seconds()) <= 2,
                'Original post no longer confirmed queued; do not edit')
        record['northern_edit_attempt'] = buffer.iso(buffer.now())
        persist(path, record)
        query = ('mutation EditApproved($input: EditPostInput!) { editPost(input: $input) { '
                 '... on PostActionSuccess { post { ' + buffer.POST_FIELDS + ' } } '
                 '... on MutationError { message } } }')
        result = buffer.gql(query, {'input': {'id': record['post_id'], 'text': text}}).get('editPost', {})
        require(not result.get('message'), 'Buffer rejected the approved edit: ' + str(result.get('message')))
        found = result.get('post')
    require(found and found.get('id') == record['post_id'] and found.get('text') == text and
            found.get('status') in ('scheduled', 'buffer', 'sent') and found.get('dueAt') and
            abs((buffer.parse_time(found['dueAt']) - due).total_seconds()) <= 2,
            'Edited post not verified; do not retry')
    record.update(text=text, provider_status=found['status'], provider_due_at=found['dueAt'],
                  external_url=found.get('externalLink'), northern_edit_verified=buffer.iso(buffer.now()))
    persist(path, record)
    print('STRIKING_EDIT_VERIFIED ' + json.dumps(record, ensure_ascii=False), flush=True)


def schedule():
    request, issue, text, due = load_request()
    path = receipt_path(request['date'])
    record = json.loads(path.read_text()) if path.exists() else None
    if request.get('owner_approval') == 'woods-to-wheels-northern-2026-11-23' and text == "One New Brunswick hardwood producer used about a U.S. gallon of diesel per green short ton just to get logs to the roadside, before the haul to the mill. That’s about $6 per ton at US$6 a gallon. Source: Woods to Wheels, The Forest Business School.":
        return edit_northern_once(path, record, text, due)
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
    # Steve requires no image at all. The canonical issue advertises an X card,
    # and Buffer exposes no X card-suppression control. Preserve the caption/link
    # and do not publish a replacement morning-card preview or remove the link.
    # Existing accepted/ambiguous attempts above remain immutable.
    # From November 15 onward, no new striking image is attached. A
    # link-free, exactly authored caption is safe as a native text-only post:
    # there is no URL from which X can generate the morning Digest preview.
    # URL-bearing captions still fail closed without a verified no-preview path.
    text_only = (request['date'] >= '2026-11-15' and
                 not any(marker in text.lower() for marker in ('http://', 'https://', 'www.')))
    if request['date'] >= '2026-11-15' and not text_only:
        raise ValueError('STRIKING_NO_IMAGE_HOLD: native images disabled; canonical link can '
                         'generate an X image preview. No safe no-preview link verified. '
                         'Caption and link preserved; no provider mutation.')
    require(due > buffer.now()+timedelta(seconds=90), 'Striking schedule deadline missed; never post immediately')
    require(adapter.fetch_public(adapter.SITE_ROOT + issue['url'])[0] == 200,
            'Canonical dated issue not publicly reachable')
    visual = None
    if request['date'] >= striking_visual.POLICY_START and not text_only:
        visual = striking_visual.describe(issue, ROOT)
        status, body, _ = adapter.fetch_public(visual['url'])
        require(status == 200 and hashlib.sha256(body).hexdigest() == visual['sha256'],
                'Exact distinct striking image is not public; do not substitute the morning card')
    record = {'date':request['date'],'text':text,'due_at':buffer.iso(due),
              'channel_id':CHANNEL_ID,'state':'attempt_started',
              'attempt_started_at':buffer.iso(buffer.now()),
              'post_id':None,'history_checked':len(posts),'source':'native-daily-striking',
              'email_attempted':False, 'visual':visual}
    persist(path, record)
    payload = {'channelId':CHANNEL_ID, 'text':text,
               'assets':[{'image': {'url':visual['url']}}] if visual else [],
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
    if visual:
        striking_visual.validate_provider_asset(post, visual)


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
        if record.get('visual'):
            striking_visual.validate_provider_asset(found, record['visual'])
        print('STRIKING_SCHEDULE_VERIFIED; publication pending scheduled time', flush=True)
        return
    delay = due.timestamp()+95-time.time()
    if delay > 0:
        require(delay < 1500, 'Post-delivery verification wait exceeds bound')
        time.sleep(delay)
    posts, found = history(text)
    require(found and found.get('id') == record['post_id'], 'Buffer returned a different striking post')
    if record.get('visual'):
        striking_visual.validate_provider_asset(found, record['visual'])
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


