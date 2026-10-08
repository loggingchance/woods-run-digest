"""Pure delivery-policy resolution. No network requests or publications."""
from __future__ import annotations
import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('America/Denver')
CHANNELS = ['x', 'instagram', 'youtube']


def stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def aware(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('A delivery timestamp must include a timezone')
    return dt.astimezone(timezone.utc)


def resolve(policy: dict, at: datetime) -> dict | None:
    if at.tzinfo is None:
        raise ValueError('Current time must include a timezone')
    local = at.astimezone(ZONE)
    date = local.date().isoformat()
    candidates = []
    for test in policy.get('tests', []):
        if not test.get('enabled') or test.get('date') != date:
            continue
        start, due = aware(test['queue_after']), aware(test['due_at'])
        if due <= start or due.astimezone(ZONE).date() != local.date():
            raise ValueError('Invalid authorized test window')
        if start <= at < due - timedelta(seconds=60):
            test_id = test['test_run_id']
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', test_id):
                raise ValueError('Invalid test ID')
            candidates.append({'action': 'schedule_test', 'date': date,
                               'test_run_id': test_id, 'due_at': stamp(due),
                               'channels': CHANNELS.copy(), 'verify_only': False})
    if len(candidates) > 1:
        raise ValueError('Overlapping authorized tests; refusing ambiguous delivery')
    if candidates:
        return candidates[0]
    daily = policy.get('daily', {})
    if daily.get('enabled'):
        due = datetime.combine(local.date(), time.fromisoformat(daily['time']), ZONE)
        start = datetime.combine(local.date(), time.fromisoformat(daily['queue_after']), ZONE)
        if start <= local < due - timedelta(seconds=60):
            return {'action': 'schedule_daily', 'date': date, 'due_at': stamp(due),
                    'channels': CHANNELS.copy(), 'verify_only': False}
    return None


def load_policy(root: Path) -> dict:
    policy = json.loads((root / 'data/delivery-policy.json').read_text(encoding='utf-8'))
    if policy.get('timezone') != 'America/Denver':
        raise ValueError('Unexpected delivery timezone')
    return policy
