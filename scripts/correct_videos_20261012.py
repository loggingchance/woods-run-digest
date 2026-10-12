#!/usr/bin/env python3
"""One-off IG/YT approved-format replacement; disabled until verified media is activated."""
import hashlib
import json
import os
import re
import struct
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import post_to_buffer as adapter
import buffer_queue

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / 'data/corrections/videos-2026-10-12-request.json'
RECEIPT = ROOT / 'data/corrections/videos-2026-10-12-receipt.json'
DATE = '2026-10-12'
PAGE = adapter.SITE_ROOT + '/2026/10/12/'
ACTIVATION = 'PUBLISH_APPROVED_V4_IG_YT_20261012'
CHANNELS = {
    'instagram': {'id': '6844cc71d6d25b49a1de682e', 'name': 'northeastforests',
                  'old_id': '6acca254c71503307d6d003c', 'old_external': 'DeY-DitAPn0'},
    'youtube': {'id': '6ab14319ea19ca0bdea627e2', 'name': 'Logging Chance',
                'old_id': '6acca256712ba82086b3e48e', 'old_external': 'QOsPOsMLgdg'},
}

def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate_request(r):
    require(r.get('mode') in ('disabled', 'audit', 'publish'), 'Invalid mode')
    if r['mode'] == 'disabled':
        return
    require(re.fullmatch(r'[a-f0-9]{40}', r.get('media_commit') or ''), 'Missing immutable media commit')
    require(re.fullmatch(r'[a-f0-9]{64}', r.get('media_sha256') or ''), 'Missing verified video hash')
    require(r.get('format') == 'approved-v4' and r.get('visual_review_confirmed') is True,
            'Approved-format visual review not confirmed')
    if r['mode'] == 'publish':
        require(r.get('activation') == ACTIVATION and r.get('parent_media_confirmed') is True,
                'Awaiting parent confirmation of exact final media')
        require(bool(r.get('authorization_reference')), 'Missing publication authorization reference')
        require(datetime.now(ZoneInfo('America/Denver')).date().isoformat() == DATE,
                'One-off publishing date expired')


def public(url):
    status, data, _ = adapter.fetch_public(url)
    require(status == 200, 'Public resource unavailable: ' + url)
    return data


def duration(data):
    def scan(start, end):
        pos = start
        while pos + 8 <= end:
            size, kind = struct.unpack_from('>I4s', data, pos)
            header = 8
            if size == 1:
                size = struct.unpack_from('>Q', data, pos + 8)[0]
                header = 16
            elif size == 0:
                size = end - pos
            require(size >= header and pos + size <= end, 'Invalid MP4 container')
            payload = pos + header
            if kind == b'mvhd':
                version = data[payload]
                require(version in (0, 1), 'Unknown MP4 timing version')
                offset = 20 if version else 12
                scale = struct.unpack_from('>I', data, payload + offset)[0]
                ticks = struct.unpack_from('>Q' if version else '>I', data, payload + offset + 4)[0]
                require(scale > 0, 'Invalid MP4 timescale')
                return ticks / scale
            if kind == b'moov':
                result = scan(payload, pos + size)
                if result is not None:
                    return result
            pos += size
    result = scan(0, len(data))
    require(result is not None, 'MP4 movie duration missing')
    return result


def persist(record):
    RECEIPT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    for command in [
        ['git', 'config', 'user.name', 'github-actions[bot]'],
        ['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'],
        ['git', 'add', str(RECEIPT.relative_to(ROOT))],
        ['git', 'commit', '-m', 'Record targeted approved-format IG and YouTube corrections'],
        ['git', 'fetch', 'origin', 'main'], ['git', 'rebase', 'origin/main'],
        ['git', 'push', 'origin', 'HEAD:main'],
    ]:
        subprocess.run(command, cwd=ROOT, check=True)


def get_post(post_id):
    return adapter.graphql('query One($id: PostId!) { post(input: {id: $id}) { '
                           + buffer_queue.POST_FIELDS + ' } }', {'id': post_id})['post']


def choose_existing(posts, target, media_url, text, receipt):
    candidates = [p for p in posts if p['id'] != target['old_id'] and
                  (PAGE in (p.get('text') or '') or any(a.get('source') == media_url for a in p.get('assets', [])))]
    require(len(candidates) <= 1, 'Multiple replacement candidates; no new post created')
    if candidates:
        p = candidates[0]
        require(p.get('text') == text and media_url in [a.get('source') for a in p.get('assets', [])],
                'Another same-date post differs; reconcile before publishing')
        return p
    require(not receipt.get('attempt_started_at'), 'Previous attempt unresolved; no automatic resubmission')
    return None


def payload_for(key, target, old_receipt, media_url, issue):
    text = old_receipt['provider_text']
    require(PAGE in text, 'Original caption lacks canonical dated link')
    if key == 'youtube':
        require(text.count('Steven Bick’s ') == 1, 'Original YouTube attribution changed')
        text = text.replace('Steven Bick’s ', 'The ', 1)
        meta = {'youtube': {'title': adapter.compose_youtube_title(issue), 'categoryId': '27',
                           'privacy': 'public', 'madeForKids': False, 'notifySubscribers': True,
                           'embeddable': True, 'license': 'youtube'}}
        assets = [{'video': {'url': media_url}}]
    else:
        meta = {'instagram': {'type': 'reel', 'shouldShareToFeed': True}}
        assets = [{'video': {'url': media_url, 'metadata': {'thumbnailOffset': 1500}}}]
    require('Steven Bick' not in text, 'Old attribution remains')
    return {'channelId': target['id'], 'text': text, 'assets': assets, 'metadata': meta,
            'mode': 'shareNow', 'schedulingType': 'automatic',
            'source': 'woods-run-approved-v4-correction-20261012',
            'saveToDraft': False, 'needsApproval': False}


def main():
    request = json.loads(REQUEST.read_text())
    validate_request(request)
    if request['mode'] == 'disabled':
        print('VIDEO_CORRECTION_DISABLED: awaiting verified immutable media and parent confirmation; no Buffer calls')
        return
    media_url = ('https://raw.githubusercontent.com/loggingchance/woods-run-digest/' +
                 request['media_commit'] + '/assets/videos/2026-10-12.mp4')
    data = public(media_url)
    require(hashlib.sha256(data).hexdigest() == request['media_sha256'], 'Video hash mismatch')
    require((1080, 1920) in buffer_queue.mp4_dimensions(data), 'Video is not 1080x1920')
    seconds = duration(data)
    require(abs(seconds - 41.5) <= 0.05, 'Video does not match approved 41.5-second format')
    issues = json.loads(public(adapter.SITE_ROOT + '/data/issues.json'))
    issue = next(i for i in issues if i.get('date') == DATE)
    require('Steve' not in issue.get('summary', ''), 'Canonical lead still contains owner attribution')
    html = public(PAGE).decode()
    require('Today’s lead remembers Mart Allen.' in html, 'Corrected canonical edition not live')
    old_receipts = json.loads((ROOT / 'data/buffer-delivery/daily-2026-10-12.json').read_text())['channels']
    org, channels = buffer_queue.get_channels()
    record = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {
        'date': DATE, 'media_url': media_url, 'media_sha256': request['media_sha256'],
        'duration_seconds': seconds, 'format': 'approved-v4', 'channels': {},
        'authorization_reference': request.get('authorization_reference'), 'old_posts_deleted': False}
    require(record['media_sha256'] == request['media_sha256'], 'Existing correction uses other media')
    prepared = {}
    # Validate both destinations and full histories before any mutation.
    for key, target in CHANNELS.items():
        channel = next((c for c in channels if c['id'] == target['id']), {})
        require(channel.get('name') == target['name'] and channel.get('service') == key,
                'Channel identity mismatch: ' + key)
        require(not any(channel.get(k) for k in ('isDisconnected', 'isLocked', 'isQueuePaused')),
                'Channel not ready: ' + key)
        old = get_post(target['old_id'])
        require(old.get('channelId') == target['id'] and target['old_external'] in (old.get('externalLink') or ''),
                'Original post identity mismatch: ' + key)
        payload = payload_for(key, target, old_receipts[key], media_url, issue)
        posts = buffer_queue.recent(org, target['id'])
        state = record['channels'].get(key, {})
        existing = choose_existing(posts, target, media_url, payload['text'], state)
        prepared[key] = {'payload': payload, 'existing': existing, 'history_count': len(posts)}
    if request['mode'] == 'audit':
        print('VIDEO_CORRECTION_AUDIT ' + json.dumps({'media_url': media_url, 'sha256': request['media_sha256'],
                                                   'duration_seconds': seconds, 'channels': prepared}, ensure_ascii=False))
        return
    require(os.environ.get('GITHUB_ACTIONS') == 'true', 'Publication requires established GitHub runtime')
    for key, info in prepared.items():
        state = record['channels'].setdefault(key, {})
        existing = info['existing']
        if not existing:
            state.update(attempt_started_at=datetime.now(timezone.utc).isoformat(), payload=info['payload'], state='attempt_started')
            persist(record)
            response = adapter.graphql('mutation Correct($input: CreatePostInput!) { createPost(input: $input) {'
                                       ' ... on PostActionSuccess { post { ' + buffer_queue.POST_FIELDS + ' } }'
                                       ' ... on MutationError { message } } }', {'input': info['payload']})['createPost']
            require(not response.get('message'), 'Buffer rejected ' + key + ': ' + str(response.get('message')))
            existing = response.get('post')
            require(existing and existing.get('id'), 'No Buffer receipt; reconcile before retry')
            state.update(replacement=existing, state='accepted')
            persist(record)
        for attempt in range(30):
            post = get_post(existing['id'])
            require(post.get('channelId') == CHANNELS[key]['id'] and post.get('text') == info['payload']['text'],
                    'Replacement identity mismatch')
            require(post.get('status') != 'error', 'Buffer publishing error: ' + json.dumps(post))
            if post.get('status') == 'sent' and post.get('externalLink'):
                state.update(replacement=post, state='sent', verified_at=datetime.now(timezone.utc).isoformat())
                persist(record)
                print('VIDEO_CORRECTION_SENT ' + key + ' ' + json.dumps(post, ensure_ascii=False), flush=True)
                break
            if attempt == 29:
                raise ValueError('Accepted but sent status not confirmed: ' + key + '; do not resubmit')
            time.sleep(10)
    print('VIDEO_CORRECTIONS_COMPLETE ' + json.dumps(record, ensure_ascii=False))

if __name__ == '__main__':
    main()
