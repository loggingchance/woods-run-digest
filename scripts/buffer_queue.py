#!/usr/bin/env python3
"""Native Buffer scheduling with run-specific receipts; never sends email."""
from __future__ import annotations
import argparse
import json
import re
import struct
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import post_to_buffer as adapter

ROOT = Path(__file__).resolve().parents[1]
DENVER = ZoneInfo('America/Denver')
TARGETS = {
    'x': ('twitter', 'ForestBizSchool', '6843193ed6d25b49a145ff6e'),
    'instagram': ('instagram', 'northeastforests', '6844cc71d6d25b49a1de682e'),
    'youtube': ('youtube', 'Logging Chance', '6ab14319ea19ca0bdea627e2'),
}
BLOCKING = {'sent', 'scheduled', 'sending', 'processing', 'buffer', 'pending'}
POST_FIELDS = 'id text status createdAt dueAt channelId externalLink assets { source mimeType }'

def now():
    return datetime.now(timezone.utc)

def iso(value):
    return value.isoformat().replace('+00:00', 'Z')

def parse_time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('A delivery time must include its UTC offset')
    return result.astimezone(timezone.utc)

def gql(query, variables=None):
    try:
        return adapter.graphql(query, variables)
    except SystemExit as exc:
        raise RuntimeError('Buffer request failed; see preceding provider error') from exc

def probe(url, required=(), media_type=None):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'WoodsRunVerification/2.0'})
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read(2_000_000)
            text = body.decode('utf-8', errors='replace')
            binary_ok = (media_type is None or
                         (media_type == 'png' and body.startswith(b'\x89PNG\r\n\x1a\n')) or
                         (media_type == 'mp4' and body[4:8] == b'ftyp'))
            return {'url': url, 'final_url': response.url, 'http_status': response.status,
                    'content_type': response.headers.get('Content-Type', ''),
                    'content_verified': response.status == 200 and binary_ok and all(s in text for s in required)}
    except Exception as exc:
        return {'url': url, 'content_verified': False, 'error': str(exc)[:350]}

def mp4_dimensions(data):
    dimensions = []
    def boxes(start, end):
        pos = start
        while pos + 8 <= end:
            size, kind = struct.unpack_from('>I4s', data, pos)
            header = 8
            if size == 1:
                if pos + 16 > end: break
                size = struct.unpack_from('>Q', data, pos + 8)[0]
                header = 16
            elif size == 0: size = end - pos
            if size < header or pos + size > end: break
            if kind in (b'moov', b'trak'):
                boxes(pos + header, pos + size)
            elif kind == b'tkhd' and size >= header + 8:
                w, h = struct.unpack_from('>II', data, pos + size - 8)
                if w and h: dimensions.append((w >> 16, h >> 16))
            pos += size
    boxes(0, len(data))
    return dimensions

def load_issue(date):
    items = json.loads((ROOT / 'data/issues.json').read_text())
    issue = next((item for item in items if item.get('date') == date), None)
    if not issue: raise ValueError('No matching dated issue')
    if date != now().astimezone(DENVER).date().isoformat():
        raise ValueError('Refusing to schedule a stale issue')
    return issue

def preflight(issue, channels):
    result = {'page': probe(adapter.SITE_ROOT + issue['url'], [issue['displayDate']])}
    if not result['page']['content_verified']:
        raise ValueError('Public dated issue not verified: ' + json.dumps(result))
    raw = 'https://raw.githubusercontent.com/loggingchance/woods-run-digest/main'
    for key, folder, extension in [('card', 'cards', 'png'), ('video', 'videos', 'mp4')]:
        if key == 'card' and 'x' not in channels: continue
        if key == 'video' and not set(channels).intersection({'instagram', 'youtube'}): continue
        path = ROOT / 'assets' / folder / (issue['date'] + '.' + extension)
        data = path.read_bytes()
        if key == 'card':
            if data[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('Invalid PNG')
            dims = struct.unpack_from('>II', data, 16)
            if dims != (1200, 630): raise ValueError('X card must be 1200x630')
        else:
            dims = mp4_dimensions(data)
            if (1080, 1920) not in dims: raise ValueError('Vertical MP4 must contain a 1080x1920 video track')
        url = f'{raw}/assets/{folder}/{issue["date"]}.{extension}'
        public = probe(url, media_type=extension)
        if not public['content_verified']:
            raise ValueError('Public asset unavailable or wrong media type: ' + json.dumps(public))
        result[key] = {'url': url, 'dimensions': dims, 'bytes': len(data), 'public': public}
    return result

def get_channels():
    organization = adapter.get_organization_id()
    query = '''query Channels($organizationId: OrganizationId!) {
      channels(input: {organizationId: $organizationId}) {
        id name service serviceId externalLink isDisconnected isLocked isQueuePaused timezone
      }
    }'''
    return organization, gql(query, {'organizationId': organization}).get('channels', [])

def recent(organization, channel):
    query = '''query Posts($org: OrganizationId!, $channel: ChannelId!, $after: String) {
      posts(first: 100, after: $after, input: {organizationId: $org, filter: {channelIds: [$channel]},
        sort: [{field: createdAt, direction: desc}]}) {
        edges { node { ''' + POST_FIELDS + ''' } }
        pageInfo { hasNextPage endCursor }
      }
    }'''
    posts, seen_cursors, after = {}, set(), None
    for _ in range(100):
        connection = gql(query, {'org': organization, 'channel': channel, 'after': after}).get('posts', {})
        info = connection.get('pageInfo', {})
        if not isinstance(info.get('hasNextPage'), bool):
            raise ValueError('Missing Buffer pagination evidence; duplicate search is incomplete')
        for edge in connection.get('edges', []):
            post = edge['node']
            posts[post['id']] = post
        if not info['hasNextPage']:
            return list(posts.values())
        after = info.get('endCursor')
        if not after or after in seen_cursors:
            raise ValueError('Buffer pagination did not advance; duplicate search is incomplete')
        seen_cursors.add(after)
    raise ValueError('Buffer history exceeds bounded pagination; duplicate search is incomplete')

def matches(post, issue, marker, saved_id=None):
    if saved_id: return post.get('id') == saved_id
    text = post.get('text') or ''
    if marker: return marker in text
    if '[WR TEST ' in text: return False
    if issue['url'] in text or ('Woods Run Digest' in text and issue['displayDate'] in text): return True
    return any(issue['date'] in (a.get('source') or '') for a in post.get('assets', []))

def make_input(key, channel, issue, assets, due, marker):
    if key == 'x':
        text = adapter.compose_x_post(issue, adapter.SITE_ROOT + issue['url'])
        media = [{'image': {'url': assets['card']['url']}}]
        metadata = None
    elif key == 'instagram':
        text = adapter.compose_instagram_post(issue)
        media = [{'video': {'url': assets['video']['url'], 'metadata': {'thumbnailOffset': 1500}}}]
        metadata = {'instagram': {'type': 'reel', 'shouldShareToFeed': True}}
    else:
        text = adapter.compose_youtube_post(issue, adapter.SITE_ROOT + issue['url'])
        media = [{'video': {'url': assets['video']['url']}}]
        metadata = {'youtube': {'title': adapter.compose_youtube_title(issue), 'categoryId': '27',
                    'privacy': 'public', 'madeForKids': False, 'notifySubscribers': True,
                    'embeddable': True, 'license': 'youtube'}}
    if marker:
        if key == 'x':
            page = adapter.SITE_ROOT + issue['url']
            allowance = 280 - len(page) - len(marker) - 4
            text = adapter.shorten_at_word(text.split('\n\n')[0], allowance) + '\n\n' + page
        text += '\n\n' + marker
    result = {'channelId': channel['id'], 'text': text, 'assets': media,
              'mode': 'customScheduled', 'schedulingType': 'automatic', 'dueAt': due,
              'source': 'woods-run-native-scheduler', 'saveToDraft': False, 'needsApproval': False}
    if metadata: result['metadata'] = metadata
    return result

def save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')

def run(request, verify=False):
    action = request.get('action', 'schedule_daily')
    date = request.get('date', now().astimezone(DENVER).date().isoformat())
    test = action == 'schedule_test'
    if action not in ('audit', 'schedule_test', 'schedule_daily'):
        raise ValueError('Unsupported action')
    run_id = request.get('test_run_id') if test else ('audit-' if action == 'audit' else 'daily-') + date
    if not run_id or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', run_id): raise ValueError('Invalid delivery ID')
    selected = request.get('channels', ['x', 'instagram', 'youtube'])
    if not selected or any(k not in TARGETS for k in selected): raise ValueError('Invalid channels')
    marker = '[WR TEST ' + run_id + ']' if test else None
    issue = load_issue(date)
    path = ROOT / 'data/buffer-delivery' / (run_id + '.json')
    record = json.loads(path.read_text()) if path.exists() else {'run_id': run_id, 'date': date, 'channels': {}}
    record['checked_at'] = iso(now())
    record['requested_action'] = action
    record['requested_channels'] = selected
    record['required_daily_channels'] = list(TARGETS)
    target_due = datetime.combine(datetime.fromisoformat(date).date(), datetime.min.time(), DENVER).replace(hour=4).astimezone(timezone.utc)
    record['daily_target_due_at'] = iso(target_due)
    organization, channels = get_channels()
    record['channel_identity'] = channels
    # Explicit authorized recovery due time overrides a prior partial receipt.
    due = request.get('due_at') or record.get('due_at')
    if not due and not verify and action != 'audit':
        due = iso(now() + timedelta(minutes=5)) if test else iso(datetime.combine(now().astimezone(DENVER).date(), datetime.min.time(), DENVER).replace(hour=4).astimezone(timezone.utc))
    if due: record['due_at'] = due
    if action == 'audit':
        try:
            record['preflight'] = preflight(issue, selected)
        except Exception as exc:
            record['preflight_error'] = str(exc)[:1600]
    assets = {}
    for key in selected:
        result = record['channels'].setdefault(key, {})
        try:
            service, name, channel_id = TARGETS[key]
            channel = next((c for c in channels if c['id'] == channel_id), None)
            if not channel or channel['service'] != service or channel['name'].casefold() != name.casefold():
                raise ValueError('Configured account identity mismatch')
            posts = recent(organization, channel_id)
            result['duplicate_search'] = {'complete': True, 'posts_checked': len(posts)}
            found = [p for p in posts if matches(p, issue, marker, result.get('post_id'))]
            if len(found) > 1:
                result['matching_posts'] = found
                raise ValueError('Multiple matching items; refusing another submission')
            if found:
                post = found[0]
            elif verify or action == 'audit':
                result.update({'status': 'absent', 'error': 'No matching delivery for this run ID'})
                continue
            else:
                if result.get('attempt_started_at'):
                    raise ValueError('Previous submission outcome unresolved; no automatic duplicate retry')
                if any(channel.get(k) for k in ('isDisconnected', 'isLocked', 'isQueuePaused')):
                    raise ValueError('Channel disconnected, locked, or queue paused')
                if not due or parse_time(due) < now() + timedelta(seconds=60):
                    raise ValueError('Delivery time missed; will not silently share immediately')
                if key not in assets:
                    assets[key] = preflight(issue, [key])
                    record.setdefault('preflight_by_channel', {})[key] = assets[key]
                payload = make_input(key, channel, issue, assets[key], due, marker)
                result['attempt_started_at'] = iso(now())
                save(path, record)
                query = 'mutation Schedule($input: CreatePostInput!) { createPost(input: $input) { ... on PostActionSuccess { post { ' + POST_FIELDS + ' } } ... on MutationError { message } } }'
                response = gql(query, {'input': payload}).get('createPost', {})
                if response.get('message'): raise ValueError('Buffer rejected scheduling: ' + response['message'])
                post = response.get('post')
                if not post or not post.get('id'): raise ValueError('No Buffer receipt returned')
                result['newly_created'] = True
            result.update({'post_id': post['id'], 'status': post.get('status'), 'due_at': post.get('dueAt'),
                           'created_at': post.get('createdAt'), 'external_url': post.get('externalLink'),
                           'assets': post.get('assets', []), 'provider_text': post.get('text'), 'error': None})
            result['schedule_verified'] = bool(due and post.get('dueAt') and abs((parse_time(due) - parse_time(post['dueAt'])).total_seconds()) <= 2 and post.get('status') in BLOCKING)
            result['provider_sent'] = post.get('status') == 'sent'
            result['delivery_state'] = {'buffer': 'queued', 'pending': 'queued',
                                        'scheduled': 'scheduled', 'processing': 'sending',
                                        'sending': 'sending', 'sent': 'sent',
                                        'error': 'failed', 'failed': 'failed'}.get(post.get('status'), 'unknown')
            result['existing_delivery'] = not test and post.get('status') in BLOCKING
            if post.get('status') not in BLOCKING:
                result['error'] = 'Buffer status is not scheduled or delivered: ' + str(post.get('status'))
            result['public_visibility'] = 'not_independently_verified'
            if post.get('externalLink'):
                result['public_probe'] = probe(post['externalLink'], [marker] if marker else [issue['displayDate']])
                if result['public_probe']['content_verified']: result['public_visibility'] = 'verified'
        except Exception as exc:
            result['error'] = str(exc)[:1200]
        save(path, record)
    record['all_scheduled'] = all(record['channels'][k].get('schedule_verified') and not record['channels'][k].get('error') for k in selected)
    record['daily_idempotent'] = not test and all(record['channels'][k].get('existing_delivery') and not record['channels'][k].get('error') for k in selected)
    record['all_provider_sent'] = all(record['channels'][k].get('provider_sent') and not record['channels'][k].get('error') for k in selected)
    record['all_public_verified'] = all(record['channels'][k].get('public_visibility') == 'verified' for k in selected)
    record['all_daily_channels_provider_sent'] = all(record['channels'].get(k, {}).get('provider_sent') and not record['channels'].get(k, {}).get('error') for k in TARGETS)
    record['all_daily_channels_scheduled'] = all(
        (entry := record['channels'].get(k, {})).get('schedule_verified')
        and not entry.get('error') and entry.get('due_at')
        and parse_time(entry['due_at']) == target_due for k in TARGETS)
    record['email_verified'] = False
    record['complete'] = False
    save(path, record)
    print('BUFFER_RECEIPT ' + json.dumps(record, ensure_ascii=False))
    if action == 'audit': return 0
    return 0 if (record['all_provider_sent'] if verify else (record['all_scheduled'] or record['daily_idempotent'])) else 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        request = json.loads((ROOT / 'data/social-trigger.json').read_text())
        raise SystemExit(run(request, args.verify))
    except Exception as exc:
        print('BUFFER_ERROR ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
