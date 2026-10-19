#!/usr/bin/env python3
"""Refresh the standing daily striking handoff; never contact a provider."""
import hashlib
import json
import os
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DENVER = ZoneInfo('America/Denver')


def prepare(root, now):
    local = now.astimezone(DENVER)
    # Both UTC cron slots run year-round; only the Denver 9 AM slot hands off.
    if local.hour != 9:
        return False
    date = local.date().isoformat()
    issues = json.loads((root / 'data/issues.json').read_text())
    issue = next((i for i in issues if i.get('date') == date), None)
    if not issue or not 0 < len(issue.get('strikingText', '').strip()) <= 280:
        raise ValueError('Current-day striking observation missing or invalid')
    if issue.get('url') != '/' + date.replace('-', '/') + '/':
        raise ValueError('Canonical dated issue URL mismatch')
    page = (root / date.replace('-', '/') / 'index.html').read_bytes()
    source = hashlib.sha256(json.dumps(issue, sort_keys=True, ensure_ascii=False).encode() + b'\n' + page).hexdigest()
    receipt = json.loads((root / 'data/preparation' / (date + '.json')).read_text())
    if receipt.get('date') != date or not receipt.get('ready') or receipt.get('source_sha256') != source:
        raise ValueError('Current editorial source has not completed preparation')
    due = datetime.combine(local.date(), time(10), DENVER).astimezone(timezone.utc)
    request = {'action': 'schedule_striking', 'date': date,
               'due_at': due.isoformat().replace('+00:00', 'Z'),
               'requestedAt': now.isoformat(),
               'reason': 'Standing daily striking handoff from verified current preparation'}
    (root / 'data/striking-trigger.json').write_text(json.dumps(request, indent=2) + '\n')
    return True


if __name__ == '__main__':
    ready = prepare(ROOT, datetime.now(timezone.utc))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('should_run=' + str(ready).lower() + '\n')
    print('Current striking handoff prepared' if ready else 'Outside Denver handoff hour; no provider action')
