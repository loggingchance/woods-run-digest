#!/usr/bin/env python3
"""Native Buffer handoff after preparation; never sends or schedules email."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from delivery_policy import aware, load_policy, resolve, stamp

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / '.delivery-request.json'


def validate_source(root: Path, request: dict) -> None:
    date = request['date']
    issue = next((i for i in json.loads((root / 'data/issues.json').read_text()) if i.get('date') == date), None)
    if not issue:
        raise ValueError('No current-date issue')
    page = (root / date.replace('-', '/') / 'index.html').read_bytes()
    source = hashlib.sha256(json.dumps(issue, sort_keys=True, ensure_ascii=False).encode() + b'\n' + page).hexdigest()
    record = json.loads((root / 'data/preparation' / (date + '.json')).read_text())
    if record.get('date') != date or not record.get('ready') or record.get('source_sha256') != source:
        raise ValueError('Preparation receipt does not match current editorial source')
    for label in ('card', 'video'):
        asset = record[label]
        path = (root / asset['path']).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('Invalid media path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
            raise ValueError(label + ' changed after preparation')


def emit_output(name: str, value: str) -> None:
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as target:
            target.write(f'{name}={value}\n')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-after-due', action='store_true')
    parser.add_argument('--legacy-request', action='store_true')
    args = parser.parse_args()
    import buffer_queue
    if args.verify_after_due:
        request = json.loads(REQUEST.read_text())
        due = aware(request['due_at'])
        # This wait controls verification only. Buffer already owns publication timing.
        for lag in (90, 240):
            delay = due.timestamp() + lag - time.time()
            if delay > 5400:
                raise ValueError('Verification wait exceeds operational limit')
            if delay > 0:
                time.sleep(delay)
            result = buffer_queue.run(request, verify=True)
            if result == 0:
                return 0
        return result
    if args.legacy_request:
        request = json.loads((ROOT / 'data/social-trigger.json').read_text())
    else:
        request = resolve(load_policy(ROOT), datetime.now(timezone.utc))
    if request is None:
        emit_output('has_request', 'false')
        local = datetime.now(__import__('zoneinfo').ZoneInfo('America/Denver'))
        receipt_path = ROOT / 'data/buffer-delivery' / ('daily-' + local.date().isoformat() + '.json')
        receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
        if all(receipt.get('channels', {}).get(k, {}).get('provider_sent') and not receipt['channels'][k].get('error') for k in ('x', 'instagram', 'youtube')):
            print('EXISTING_DELIVERY: all three channels already sent; no posts created')
            return 0
        raise ValueError('NO_DELIVERY_WINDOW: no posts created; all-three-channel daily delivery is not established')
    verify_only = bool(request.get('verify_only'))
    if not verify_only and request['action'] != 'audit':
        validate_source(ROOT, request)
    REQUEST.write_text(json.dumps(request, indent=2) + '\n')
    emit_output('has_request', 'true')
    emit_output('should_verify', str(not verify_only and request['action'] != 'audit').lower())
    print('RESOLVED_REQUEST ' + json.dumps(request))
    return buffer_queue.run(request, verify=verify_only)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('HANDOFF_FAILURE ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
