"""Adapt an edition's already selected resource for video and captions.

This module never reads the resource catalog, advances a rotation, or fetches a
remote page. Explicit unavailable metadata is authoritative, including on retry.
"""
from datetime import date as Date
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

HEADING = "Today's Featured Resource"


class _Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def descendants(self):
        for child in self.children:
            if isinstance(child, _Node):
                yield child
                yield from child.descendants()

    def first(self, predicate):
        return next((node for node in self.descendants() if predicate(node)), None)

    def text(self):
        if self.tag in ('script', 'style'):
            return ''
        return ' '.join(child.text() if isinstance(child, _Node) else child
                        for child in self.children)

    def has_class(self, name):
        return name in (self.attrs.get('class') or '').split()


class _HTMLTree(HTMLParser):
    """Small read-only DOM for known edition markup; no optional dependencies."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = _Node()
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def resource_text(value):
    """Plain display text, including the approved Fieldbook name correction."""
    text = _HTMLTree(str(value or '')).root.text()
    text = ' '.join(text.split())
    text = re.sub(r"\b(?:The\s+)?Forester[’']s Fieldbook\b",
                  'The Forester’s Fieldbook', text, flags=re.IGNORECASE)
    return text


def _resource(item):
    if not isinstance(item, dict):
        raise ValueError('Featured resource item must be an object or null')
    title = re.sub(r'^(?:app|book|website)\s*:\s*', '', resource_text(item.get('title')),
                   flags=re.IGNORECASE)
    description = resource_text(item.get('description'))
    description = re.sub(r'^(?:app|book|website)\s*:\s*', '', description,
                         flags=re.IGNORECASE)
    url = str(item.get('url') or item.get('source_url') or '').strip()
    parsed = urlsplit(url)
    if (not title or not description or parsed.scheme not in ('http', 'https')
            or not parsed.hostname or parsed.username or parsed.password
            or any(c.isspace() or ord(c) < 32 for c in url)):
        raise ValueError('Featured resource requires a title, description and safe HTTP(S) URL')
    return dict(title=title, description=description, url=url,
                kind=resource_text(item.get('kind')))


def read_featured_resource(source, date, issue=None):
    """Read only this date's selection, with a dated-HTML legacy fallback.

    Metadata wins whenever its key exists. A null item yields no slide/caption;
    malformed or wrong-date metadata fails rather than substituting a choice.
    HTML fallback is permitted only when the metadata key is absent.
    """
    source = Path(source)
    if Date.fromisoformat(date).isoformat() != date:
        raise ValueError('Featured resource date must be YYYY-MM-DD')
    if issue is None:
        metadata = source / 'data/issues.json'
        issues = json.loads(metadata.read_text(encoding='utf-8')) if metadata.is_file() else []
        issue = next((entry for entry in issues if entry.get('date') == date), {})
    if issue.get('date') and issue['date'] != date:
        raise ValueError('Featured resource issue date mismatch')
    if 'featuredResource' in issue:
        selection = issue['featuredResource']
        if selection is None:
            return None
        if not isinstance(selection, dict):
            raise ValueError('Featured resource selection must be an object')
        if selection.get('date') and selection['date'] != date:
            raise ValueError('Featured resource selection date mismatch')
        if 'item' not in selection:
            raise ValueError('Featured resource selection is missing item')
        return None if selection['item'] is None else _resource(selection['item'])

    page = source / date.replace('-', '/') / 'index.html'
    if not page.is_file():
        return None
    document = _HTMLTree(page.read_text(encoding='utf-8')).root
    boxes = []
    for section in document.descendants():
        if section.tag != 'section' or not any(section.has_class(name) for name in
                ('wet-woods-box', 'featured-resource', 'featured-resources')):
            continue
        heading = section.first(lambda node: node.has_class('section-kicker') or node.tag == 'h2')
        label = resource_text(heading.text() if heading else '')
        if label.lower().replace('’', "'") in ("today's featured resource", "today's featured resources", 'books & apps'):
            boxes.append(section)
    if not boxes:
        return None
    if len(boxes) != 1:
        raise ValueError('Edition has multiple featured resource boxes')
    box = boxes[0]
    title = box.first(lambda node: node.tag == 'h3') or box.first(lambda node: node.tag == 'h2')
    link = (box.first(lambda node: node.tag == 'a' and node.has_class('book-button') and node.attrs.get('href'))
            or box.first(lambda node: node.tag == 'a' and node.attrs.get('href')))
    if not link:
        return None  # The canonical unavailable notice has no resource link.
    paragraphs = [node.text() for node in box.descendants()
                  if node.tag == 'p' and not node.has_class('section-kicker')
                  and not node.first(lambda child: child.tag == 'a')]
    return _resource(dict(title=title.text() if title else '',
                          description=' '.join(paragraphs), url=link.attrs.get('href')))



def featured_resource_caption(issue, source):
    """A caption suffix shared by Instagram and YouTube; never used for X."""
    if not issue.get('date'):
        return ''
    resource = read_featured_resource(source, issue['date'], issue)
    if resource is None:
        return ''
    return f"\n\n{HEADING}\n{resource['title']}\n{resource['url']}"
