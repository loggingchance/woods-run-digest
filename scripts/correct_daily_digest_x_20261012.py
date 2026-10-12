#!/usr/bin/env python3
"""One-off original daily Digest X correction. Audit by default; never deletes a post."""
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import post_to_buffer as adapter
import buffer_queue

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / 'data/corrections/daily-digest-x-2026-10-12-request.json'
RECEIPT = ROOT / 'data/corrections/daily-digest-x-2026-10-12-receipt.json'
DATE = '2026-10-12'
CHANNEL = '6843193ed6d25b49a145ff6e'
OLD_BUFFER = '6acca251712ba82086b3e38c'
OLD_X = '2109584944016113910'
PAGE = adapter.SITE_ROOT + '/2026/10/12/'
PHOTO = 'https://raw.githubusercontent.com/loggingchance/woods-run-digest/main/assets/cards/2026-10-12.png'
PHOTO_HASH = 'affb6d3eed2326c5867750f181f24650dcdba686a9c24cc30169137b126e300f'
SOCIAL = 'Mart Allen, Adirondack Forester and Friend to Many, Dies at 99. Remembering Mart Allen (1927–2026), Adirondack woodsman, ranger and friend. The full personal tribute leads the October 12 Woods Run Digest.'
ACTIVATION = 'PUBLISH_ORIGINAL_DAILY_DIGEST_X_20261012'
FIELDS = buffer_queue.POST_FIELDS + ' allowedActions'


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_request(request):
    require(request.get('old_buffer_id') == OLD_BUFFER and request.get('old_x_id') == OLD_X,
            'Incorrect target post')
    require(request.get('mode') in ('audit', 'publish'), 'Invalid correction mode')
    if request['mode'] == 'publish':
        require(request.get('activation') == ACTIVATION, 'Publishing is not activated')
        deleted = request.get('owner_confirmed_old_x_deleted') is True
        owner_handles = (request.get('owner_handles_deletion') is True and
                         request.get('owner_allows_replacement_before_deletion') is True)
        require(deleted or owner_handles,
                'Awaiting owner confirmation or explicit authorization to post before deletion')
        require(bool(request.get('authorization_reference')), 'Missing authorization reference')
        require(datetime.now(ZoneInfo('America/Denver')).date().isoformat() == DATE,
                'One-off publication date expired; no post created')


def fetch_post(post_id):
    return adapter.graphql('query OnePost($id: PostId!) { post(input: {id: $id}) { '
                           + FIELDS + ' } }', {'id': post_id})['post']


def fetch_public(url):
    status, body, _ = adapter.fetch_public(url)
    require(status == 200, 'Public source unavailable: ' + url)
    return body


def prepare():
    issues = json.loads(fetch_public(adapter.SITE_ROOT + '/data/issues.json'))
    matches = [i for i in issues if i.get('date') == DATE]
    require(len(matches) == 1, 'Canonical issue is missing or ambiguous')
    issue = matches[0]
    require(issue.get('url') == '/2026/10/12/' and 'Steve' not in issue.get('socialText', ''),
            'Canonical corrected edition changed; review required')
    original = json.loads((ROOT / 'data/buffer-delivery/daily-2026-10-12.json').read_text())['channels']['x']
    require(original['post_id'] == OLD_BUFFER and OLD_X in original['external_url'], 'Original receipt mismatch')
    require(original['assets'][0]['source'] == PHOTO, 'Original card source mismatch')
    original_text = original['provider_text']
    require(original_text.count('Steven Bick’s ') == 1, 'Original attribution differs')
    corrected_text = original_text.replace('Steven Bick’s ', 'The ', 1)
    require(corrected_text == SOCIAL + '\n\n' + PAGE, 'Minimal caption correction mismatch')
    html = fetch_public(PAGE).decode()
    lead = html.split('<h2>By the Numbers</h2>')[0]
    require('Today’s lead remembers Mart Allen.' in lead, 'Corrected lead is not live')
    require(not re.search(r'Steve(?:n)? Bick', lead), 'Old attribution remains in live lead')
    require('/assets/mart-allen-memorial-2026-10-12.png' in lead, 'Memorial photo missing')
    require(hashlib.sha256(fetch_public(PHOTO)).hexdigest() == PHOTO_HASH, 'Original daily Digest card changed')
    text = corrected_text
    require('Steve' not in text and len(text) <= 280, 'Invalid correction text')
    return {'channelId': CHANNEL, 'text': text, 'mode': 'shareNow',
            'schedulingType': 'automatic', 'source': 'woods-run-daily-digest-correction-20261012',
            'assets': [{'image': {'url': PHOTO}}], 'saveToDraft': False, 'needsApproval': False}


def persist(record):
    """Persist the attempt BEFORE mutation; ambiguity blocks automatic resubmission."""
    RECEIPT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    commands = [
        ['git', 'config', 'user.name', 'github-actions[bot]'],
        ['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'],
        ['git', 'add', str(RECEIPT.relative_to(ROOT))],
        ['git', 'commit', '-m', 'Record one-off original Digest X correction state'],
        ['git', 'fetch', 'origin', 'main'],
        ['git', 'rebase', 'origin/main'],
        ['git', 'push', 'origin', 'HEAD:main'],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)


def select_existing(posts, text, receipt):
    candidates = [p for p in posts if p.get('id') not in (OLD_BUFFER, '6accd289355aa519678a0307') and PAGE in (p.get('text') or '')]
    require(len(candidates) <= 1, 'Multiple other October 12 posts exist; no new post created')
    if candidates:
        post = candidates[0]
        require(post.get('text') == text, 'Different same-edition post exists; manual reconciliation required')
        require(PHOTO in [a.get('source') for a in post.get('assets', [])],
                'Existing candidate photo does not match; no duplicate created')
        return post
    require(not receipt.get('attempt_started_at'), 'Previous attempt unresolved; no automatic resubmission')
    return None


def main():
    request = json.loads(REQUEST.read_text())
    validate_request(request)
    payload = prepare()
    org, channels = buffer_queue.get_channels()
    channel = next((c for c in channels if c['id'] == CHANNEL), {})
    require(channel.get('name') == 'ForestBizSchool' and channel.get('service') == 'twitter',
            'X channel identity mismatch')
    require(not any(channel.get(k) for k in ('isDisconnected', 'isLocked', 'isQueuePaused')),
            'X channel is not ready')
    old = fetch_post(OLD_BUFFER)
    require(old.get('channelId') == CHANNEL and OLD_X in (old.get('externalLink') or ''),
            'Old Buffer post does not match exact X target')
    posts = buffer_queue.recent(org, CHANNEL)
    receipt = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {}
    existing = select_existing(posts, payload['text'], receipt)
    report = {'mode': request['mode'], 'old_post': old, 'canonical_url': PAGE,
              'photo_url': PHOTO, 'photo_sha256': PHOTO_HASH, 'proposed_text': payload['text'],
              'posts_checked': len(posts), 'replacement': existing,
              'note': 'Buffer cannot delete published X posts. The owner handles removal.'}
    if request['mode'] == 'audit':
        print('CORRECTION_AUDIT ' + json.dumps(report, ensure_ascii=False))
        return
    require(os.environ.get('GITHUB_ACTIONS') == 'true', 'Publication only allowed in existing GitHub runtime')
    if not existing:
        receipt = {'old_buffer_id': OLD_BUFFER, 'old_x_id': OLD_X,
                   'authorization_reference': request['authorization_reference'],
                   'owner_confirmed_old_x_deleted': request.get('owner_confirmed_old_x_deleted') is True,
                   'owner_handles_deletion': request.get('owner_handles_deletion') is True,
                   'owner_allows_replacement_before_deletion': request.get('owner_allows_replacement_before_deletion') is True,
                   'attempt_started_at': datetime.now(timezone.utc).isoformat(), 'payload': payload,
                   'state': 'attempt_started'}
        persist(receipt)
        # One mutation only. Do not retry uncertain network responses.
        response = adapter.graphql('mutation Correct($input: CreatePostInput!) { createPost(input: $input) {'
                                   ' ... on PostActionSuccess { post { ' + FIELDS + ' } }'
                                   ' ... on MutationError { message } } }', {'input': payload})['createPost']
        require(not response.get('message'), 'Buffer rejected correction: ' + str(response.get('message')))
        existing = response.get('post')
        require(existing and existing.get('id'), 'No receipt returned; reconcile before retry')
        receipt.update({'replacement': existing, 'state': 'accepted'})
        persist(receipt)
    for attempt in range(12):
        post = fetch_post(existing['id'])
        require(post.get('channelId') == CHANNEL and post.get('text') == payload['text'], 'Replacement identity mismatch')
        require(post.get('status') != 'error', 'Buffer reported publishing error: ' + json.dumps(post))
        if post.get('status') == 'sent' and post.get('externalLink'):
            receipt.update({'replacement': post, 'state': 'sent',
                            'verified_at': datetime.now(timezone.utc).isoformat()})
            persist(receipt)
            print('CORRECTION_SENT ' + json.dumps(receipt, ensure_ascii=False))
            return
        if attempt < 11:
            time.sleep(10)
    raise ValueError('Replacement accepted but sent status not confirmed; do not resubmit')


if __name__ == '__main__':
    main()
