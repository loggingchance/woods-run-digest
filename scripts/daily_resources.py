"""Canonical Sheet-backed resource selection; mirror consumers never select.

Call refresh with rows read through the existing Google connection. Persist its
result even when a draft fails; only confirm_publication consumes a resource.
No network, credentials, provider mutations or implicit disk writes occur here.
"""
import copy
import html
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

START = '2026-10-25'
HEADING = "Today's Featured Resources"
SOURCE = {'spreadsheet_id': '1xA8TQYJJh6rsBvo3JzFVSScudmvP8vqpuMw-s3u6DrU',
          'tab': 'daily', 'sheet_id': 1391345758}


def identity(url):
    if not isinstance(url, str):
        raise ValueError('Resource URL must be text')
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Invalid resource URL')
    host = parts.hostname.lower()
    port = parts.port
    if port and (parts.scheme.lower(), port) not in (('https', 443), ('http', 80)):
        host += ':' + str(port)
    return urlunsplit((parts.scheme.lower(), host, parts.path or '/', parts.query, ''))


def refresh(rows, previous=None, *, checked_at, error=None):
    """An empty successful read replaces cache; only a failed read uses cache."""
    if error is not None:
        if previous is None or previous.get('source') != SOURCE:
            return dict(source=SOURCE, entries=[], checked_at=checked_at,
                        cached=True, error=str(error), unavailable=True)
        result = copy.deepcopy(previous)
        result.update(cached=True, last_attempt_at=checked_at, error=str(error))
        return result
    if not rows or rows[0][:2] != ['Links', 'Notes']:
        raise ValueError('Expected daily tab Links, Notes columns; treat read failure explicitly')
    entries = {}
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        try:
            url = identity(row[0])
        except (ValueError, TypeError):
            continue
        entry = entries.setdefault(url, dict(url=url, notes=[]))
        note = str(row[1]).strip() if len(row) > 1 else ''
        if note and note not in entry['notes']:
            entry['notes'].append(note)
    return dict(source=SOURCE, entries=[entries[k] for k in sorted(entries)],
                checked_at=checked_at, cached=False)


def eligible(snapshot, catalog):
    """Notes are data, never instructions. Only verified descriptions are eligible."""
    assert snapshot['source'] == SOURCE
    result = {}
    for entry in snapshot['entries']:
        key = identity(entry['url'])
        item = catalog.get(key)
        if not item or not item.get('verified') or not all(item.get(k) for k in ('title', 'kind', 'description', 'source_url')):
            continue
        try:
            identity(item['source_url'])
        except (ValueError, TypeError):
            continue
        result[key] = {k: item[k] for k in ('title', 'kind', 'description', 'source_url')}
        result[key]['url'] = key
    return result


def save_private(path, value):
    """Atomically save source-only state; callers must keep path outside dist."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare(day, snapshot, catalog, state):
    """Return (selection, new state). Save new state before rendering a draft.

    One chronological canonical publisher owns state. Pending dates reserve a
    choice but never consume it. Reprepare the same date returns frozen metadata.
    """
    date.fromisoformat(day)
    if day < START:
        raise ValueError('Historical editions use their historical rotation')
    result = copy.deepcopy(state)
    selections = result.setdefault('selections', {})
    if day in selections:
        if selections[day].get('status') == 'abandoned':
            raise ValueError('This date was explicitly abandoned; do not revive it')
        return copy.deepcopy(selections[day]), result
    unresolved = sorted(d for d, s in selections.items()
                        if s.get('status') not in ('published', 'abandoned'))
    if unresolved:
        raise ValueError('Reconcile unresolved resource selections before a new date: ' + ', '.join(unresolved))
    if any(d > day and s.get('status') == 'published' for d, s in selections.items()):
        raise ValueError('Cannot backfill resource history')
    candidates = eligible(snapshot, catalog)
    used = set(result.get('used', []))
    pool = sorted(set(candidates) - used)
    cycle = result.get('cycle', 1)
    if candidates and not pool:
        pool = sorted(candidates)
        cycle += 1
    item = candidates[pool[0]] if pool else None
    selection = dict(date=day, source=SOURCE, item=item, cycle=cycle,
                     status='prepared', cached=bool(snapshot.get('cached')),
                     snapshot_checked_at=snapshot.get('checked_at'))
    if item is None:
        selection['unavailable_reason'] = 'No eligible verified resources in the daily Sheet snapshot'
    selections[day] = selection
    return copy.deepcopy(selection), result


def abandon_unpublished(day, state, *, proof):
    """Release a proven-unpublished draft without consuming its resource.

    The canonical caller must establish nonpublication independently and provide
    an auditable record. A failed/404 public fetch, missing confirmation or an
    attempted deployment with uncertain outcome is NOT proof of nonpublication.
    This operation never infers proof from a draft's local status or its age.
    """
    if (not isinstance(proof, dict) or proof.get('date') != day or
            proof.get('outcome') != 'proven_unpublished' or
            not proof.get('checked_at') or not proof.get('evidence')):
        raise ValueError('Explicit dated evidence of nonpublication is required')
    result = copy.deepcopy(state)
    selection = result['selections'][day]
    if selection.get('status') != 'prepared':
        raise ValueError('Only an unresolved prepared draft can be abandoned')
    selection.update(status='abandoned', abandonment=copy.deepcopy(proof))
    return result


def confirm_publication(day, published_issue, state):
    """Invoke ONLY after canonical public readback, also to reconcile uncertainty.

    The caller must verify the dated public page and its metadata agree before
    this call. No draft, build or attempted deployment consumes the cycle.
    """
    result = copy.deepcopy(state)
    selection = result['selections'][day]
    if selection.get('status') not in ('prepared', 'published'):
        raise ValueError('Cannot confirm an abandoned or invalid selection')
    if published_issue.get('date') != day or published_issue.get('featuredResource') != public_selection(selection):
        raise ValueError('Published resource does not match prepared selection')
    if selection['status'] == 'published':
        return result
    if any(d > day and s.get('status') == 'published' for d, s in result['selections'].items()):
        raise ValueError('Out-of-order publication; reconcile first')
    item = selection['item']
    if item:
        if selection['cycle'] == result.get('cycle', 1) and item['url'] in result.get('used', []):
            raise ValueError('Prepared selection is stale after another publication; reconcile first')
        if selection['cycle'] != result.get('cycle', 1):
            result['used'] = []
        result['cycle'] = selection['cycle']
        result['used'] = sorted(set(result.get('used', [])) | {item['url']})
    selection['status'] = 'published'
    return result


def public_selection(selection):
    # Never publish the private Sheet identity, raw rows, notes, catalog or ledger.
    return dict(date=selection['date'], source='daily-sheet', item=copy.deepcopy(selection['item']),
                cached=selection['cached'],
                **({'unavailable_reason': selection['unavailable_reason']} if selection['item'] is None else {}))


def resource_html(selection):
    item = selection['item']
    content = '<p>No featured resource is available for this edition.</p>'
    if item:
        content = ('<h2>' + html.escape(item['title']) + '</h2><p>' +
                   html.escape(item['kind'] + ': ' + item['description']) +
                   '</p><p><a class="book-button" href="' + html.escape(item['url'], quote=True) +
                   '">Explore ' + html.escape(item['title']) + ' →</a></p>')
    return '<section class="wet-woods-box"><p class="section-kicker">' + html.escape(HEADING) + '</p>' + content + '</section>'


def validate_feature(article, issue):
    """Shared mirror/email check: no reselection or hardcoded fallback."""
    selection = issue.get('featuredResource')
    if not isinstance(selection, dict) or selection.get('date') != issue['date'] or selection.get('source') != 'daily-sheet':
        raise ValueError('Missing canonical daily Sheet selection')
    boxes = [section for section in article.find_all('section')
             if section.select_one('.section-kicker') and
             section.select_one('.section-kicker').get_text(' ', strip=True) == HEADING]
    if len(boxes) != 1:
        raise ValueError('Expected exactly one canonical featured resource box')
    box = boxes[0]
    item = selection.get('item')
    if item is None:
        if not selection.get('unavailable_reason') or box.find('a', href=True):
            raise ValueError('Unavailable resource must be explicit with no fabricated link')
        if 'No featured resource is available for this edition.' not in box.get_text(' ', strip=True):
            raise ValueError('Missing resource unavailable notice')
        return None
    text = ' '.join(box.get_text(' ', strip=True).split())
    for field in ('title', 'kind', 'description'):
        if not item.get(field) or ' '.join(item[field].split()) not in text:
            raise ValueError('Canonical resource metadata/page mismatch: ' + field)
    links = [identity(a['href']) for a in box.find_all('a', href=True)]
    if not links or set(links) != {identity(item['url'])}:
        raise ValueError('Canonical resource link mismatch')
    return item
