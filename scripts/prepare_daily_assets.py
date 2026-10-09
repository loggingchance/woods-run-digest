#!/usr/bin/env python3
"""Prepare current Woods Run media without contacting Buffer or Resend."""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from buffer_queue import mp4_dimensions
from generate_social_cards import render_card


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    date = datetime.now(ZoneInfo('America/Denver')).date().isoformat()
    issues = json.loads((ROOT / 'data/issues.json').read_text(encoding='utf-8'))
    if not issues or issues[0].get('date') != date:
        raise ValueError('Preparation requires the current Denver date as the first issue record')
    issue = issues[0]
    for field in ('displayDate', 'url', 'summary', 'cardTeaser'):
        if not issue.get(field):
            raise ValueError(f'Current issue is missing {field}')
    page_path = ROOT / date.replace('-', '/') / 'index.html'
    page = page_path.read_bytes()
    if issue['displayDate'] not in page.decode('utf-8'):
        raise ValueError('Dated page and issue metadata disagree')
    source_hash = digest(json.dumps(issue, sort_keys=True, ensure_ascii=False).encode('utf-8') + b'\n' + page)
    record_path = ROOT / 'data/preparation' / (date + '.json')
    previous = json.loads(record_path.read_text()) if record_path.exists() else {}
    source_changed = bool(previous and previous.get('source_sha256') != source_hash)
    card = ROOT / 'assets/cards' / (date + '.png')
    video = ROOT / 'assets/videos' / (date + '.mp4')
    renderer_hash = digest((ROOT / 'scripts/generate_social_cards.py').read_bytes() +
                           (ROOT / 'assets/woodsrun-header.webp').read_bytes() +
                           (ROOT / 'scripts/render_daily_reel.py').read_bytes())
    renderer_changed = previous.get('renderer_sha256') != renderer_hash
    generated = []
    if renderer_changed or source_changed or not card.exists() or not card.stat().st_size:
        render_card(issue, card)
        generated.append('card')
    if renderer_changed or source_changed or not video.exists() or not video.stat().st_size:
        subprocess.run([sys.executable, 'scripts/render_daily_reel.py'], cwd=ROOT, check=True)
        generated.append('video')
    card_bytes = card.read_bytes()
    if card_bytes[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack_from('>II', card_bytes, 16) != (1200, 630):
        raise ValueError('X card is not a 1200x630 PNG')
    video_bytes = video.read_bytes()
    if (1080, 1920) not in mp4_dimensions(video_bytes):
        raise ValueError('Video does not contain a 1080x1920 track')
    record = {
        'date': date,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'source_sha256': source_hash,
        'renderer_sha256': renderer_hash,
        'page_path': str(page_path.relative_to(ROOT)),
        'ready': True,
        'generated_this_run': generated,
        'card': {'path': str(card.relative_to(ROOT)), 'dimensions': [1200, 630], 'sha256': digest(card_bytes)},
        'video': {'path': str(video.relative_to(ROOT)), 'dimensions': [1080, 1920], 'sha256': digest(video_bytes)},
        'publication_attempted': False,
        'email_attempted': False,
    }
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print('PREPARATION_READY ' + json.dumps(record))


if __name__ == '__main__':
    main()
