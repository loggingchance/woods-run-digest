#!/usr/bin/env python3
"""Mirror the current published Site, never research or invent another edition."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://woods-run-digest.steve760060.chatgpt.site'


def fetch(path):
    url = SITE + path
    with urlopen(Request(url, headers={'User-Agent': 'WoodsRunEditorialHandoff/1.0',
                                      'Cache-Control': 'no-cache'}), timeout=30) as response:
        if response.status != 200 or response.url.rstrip('/') != url.rstrip('/'):
            raise ValueError('Canonical public source unavailable or redirected')
        return response.read().decode('utf-8')


def validate(page, issue):
    day = datetime.fromisoformat(issue['date']).date()
    expected = day.strftime('%B') + f' {day.day}, {day.year}'
    if issue.get('displayDate') != expected or issue.get('url') != '/' + issue['date'].replace('-', '/') + '/':
        raise ValueError('Canonical metadata date or route mismatch')
    for field in ('summary', 'socialText', 'cardTeaser', 'cardSubhead', 'strikingText'):
        if not issue.get(field):
            raise ValueError('Missing canonical metadata: ' + field)
    soup = BeautifulSoup(page, 'html.parser')
    article = soup.select_one('article.edition-wrap')
    if not article or expected not in article.get_text(' ', strip=True):
        raise ValueError('Complete canonical dated edition not found')
    text = article.get_text(' ', strip=True)
    for section in ('By the Numbers', 'Action Detector', 'Under the Radar', 'Forest Business School'):
        if section.lower() not in text.lower():
            raise ValueError('Canonical edition missing ' + section)
    if len(article.find_all('p')) < 10 or len(article.select('article.story')) < 3:
        raise ValueError('Canonical edition is incomplete')
    return article


def sync(root, metadata, pages, day):
    if not metadata or metadata[0].get('date') != day:
        raise ValueError('Site has not published the current Denver edition')
    issue = metadata[0]
    article = validate(pages[issue['url'] + 'index.html'], issue)
    current = json.loads((root / 'data/issues.json').read_text())
    # Preserve every historical record while adopting only the current authoritative one.
    records = [issue] + [i for i in current if i['date'] != day]
    for route, page in pages.items():
        destination = root / route.lstrip('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(page, encoding='utf-8')
    (root / 'data/issues.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    receipt = {'date': day, 'checked_at': datetime.now(timezone.utc).isoformat(),
               'canonical_url': SITE + issue['url'], 'metadata_verified': True,
               'article_sha256': hashlib.sha256(str(article).encode()).hexdigest(),
               'source_links': [a['href'] for a in article.find_all('a', href=True)],
               'headlines': [h.get_text(' ', strip=True) for h in article.find_all('h3')],
               'publication_attempted': False}
    path = root / 'data/editorial-handoff' / (day + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    return receipt


def main():
    day = datetime.now(ZoneInfo('America/Denver')).date().isoformat()
    metadata = json.loads(fetch('/data/issues.json'))
    route = '/' + day.replace('-', '/') + '/'
    pages = {route + 'index.html': fetch(route), 'index.html': fetch('/'),
             'archive/index.html': fetch('/archive/'), 'sitemap.xml': fetch('/sitemap.xml')}
    print('EDITORIAL_HANDOFF_READY ' + json.dumps(sync(ROOT, metadata, pages, day)))


if __name__ == '__main__':
    main()
