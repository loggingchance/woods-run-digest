#!/usr/bin/env python3
"""Refresh the standing daily striking handoff; never contact a provider."""
import hashlib
import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DENVER = ZoneInfo('America/Denver')


def prepare(root, now):
    local = now.astimezone(DENVER)
    date = local.date().isoformat()
    trigger = root / 'data/striking-trigger.json'
    approved = json.loads(trigger.read_text()) if trigger.exists() else {}
    if (date == '2026-11-16' and approved.get('date') == date and
            approved.get('owner_approval') == 'phone-c24fc492-eefc-4d00-aa33-53c80c630526' and
            approved.get('text_only_override') == "After more than two years idle, ND Paper’s R12 machine in Rumford, Maine, produced a trial roll on November 5. A trial is not a restart: the company had not announced a return to regular production."):
        return True
    if (date == '2026-11-23' and approved.get('date') == date and
            approved.get('action') == 'schedule_striking' and
            approved.get('due_at') == '2026-11-23T17:00:00Z' and
            approved.get('owner_approval') == 'woods-to-wheels-2026-11-23' and
            approved.get('text_only_override') == "Six logging crews in a 2015 Auburn study averaged 0.51 gallons of diesel per ton of wood before it ever got on a truck. At $6 a gallon, that’s about $3 a ton in harvesting fuel alone. Source: Woods to Wheels, The Forest Business School."):
        return True
    issues = json.loads((root / 'data/issues.json').read_text())
    issue = next((i for i in issues if i.get('date') == date), None)
    weekend_feature_day = date >= '2026-11-03' and local.weekday() >= 5
    if issue and weekend_feature_day:
        if issue.get('strikingSkip') is True:
            return False
        feature = issue.get('weekendFeature') or {}
        if (issue.get('weekendFeatureStatus') != 'approved' or issue.get('strikingSource') != 'weekend_feature'
                or feature.get('kind') != ('profile' if local.weekday() == 5 else 'human_interest')
                or issue.get('strikingText') != feature.get('striking_text')):
            raise ValueError('Weekend striking post must match the approved canonical feature')
    if not issue or not issue.get('strikingText', '').strip():
        raise ValueError('Current-day striking observation missing or invalid')
    if len(issue['strikingText'].strip()) > 280:
        raise ValueError(f"Authored strikingText is {len(issue['strikingText'].strip())} characters; Buffer X maximum is 280. Correct canonical source before scheduling")
    if issue.get('url') != '/' + date.replace('-', '/') + '/':
        raise ValueError('Canonical dated issue URL mismatch')
    page = (root / date.replace('-', '/') / 'index.html').read_bytes()
    source = hashlib.sha256(json.dumps(issue, sort_keys=True, ensure_ascii=False).encode() + b'\n' + page).hexdigest()
    receipt = json.loads((root / 'data/preparation' / (date + '.json')).read_text())
    if receipt.get('date') != date or not receipt.get('ready') or receipt.get('source_sha256') != source:
        raise ValueError('Current editorial source has not completed preparation')
    due = datetime.combine(local.date(), time(10), DENVER).astimezone(timezone.utc)
    trigger = root / 'data/striking-trigger.json'
    previous = json.loads(trigger.read_text()) if trigger.exists() else {}
    delivery = root / 'data/striking-delivery' / (date + '.json')
    # Never move the requested time after an attempt, including an ambiguous one.
    if delivery.exists():
        record = json.loads(delivery.read_text())
        if record.get('text') != issue['strikingText'].strip():
            raise ValueError('Current striking content differs from existing attempt')
        if previous.get('date') != date or previous.get('due_at') != record.get('due_at'):
            raise ValueError('Existing attempt has no matching durable handoff')
        return True
    # No new striking images: preserve the authored caption and link for review.
    # One explicit user-approved recovery, not a standing late-post permission.
    recovery = (date == '2026-10-21' and previous.get('date') == date and
                previous.get('recovery_approval') == 'user-2026-10-21T21:57Z')
    if recovery:
        due = now.astimezone(timezone.utc) + timedelta(minutes=5)
        if due.astimezone(DENVER).date() != local.date():
            raise ValueError('Recovery cannot cross the issue date')
    # A verified 09:45 handoff is authoritative. Do not rewrite its timestamp,
    # requested action, or reason before the provider receives it.
    if (previous.get('action') == 'schedule_striking' and
            previous.get('date') == date and
            previous.get('due_at') == due.isoformat().replace('+00:00', 'Z') and
            previous.get('reason') == 'native Buffer scheduled daily striking observation'):
        return True
    request = {'action': 'schedule_striking', 'date': date,
               'due_at': due.isoformat().replace('+00:00', 'Z'),
               'requestedAt': now.isoformat(),
               'reason': 'Standing daily striking handoff from verified current preparation'}
    if recovery:
        request['recovery_approval'] = previous['recovery_approval']
    (root / 'data/striking-trigger.json').write_text(json.dumps(request, indent=2) + '\n')
    return True


if __name__ == '__main__':
    ready = prepare(ROOT, datetime.now(timezone.utc))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('should_run=' + str(ready).lower() + '\n')
    print('Current striking handoff prepared' if ready else 'No current striking handoff')


