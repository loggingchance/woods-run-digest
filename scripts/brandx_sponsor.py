"""Validate the approved canonical Monday sponsor; never select or send mail."""
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Comment

START = date(2026, 11, 9)


def _tree(node):
    # Ignore indentation/HTML attribute order, but no unapproved content or CSS.
    if isinstance(node, Comment):
        raise ValueError('Comments are not part of the approved sponsor panel')
    if isinstance(node, NavigableString):
        return ' '.join(str(node).split()) or None
    attrs = tuple(sorted((k, tuple(v) if isinstance(v, list) else v)
                         for k, v in node.attrs.items()))
    return (node.name, attrs, tuple(v for child in node.children
                                   if (v := _tree(child)) is not None))


def validate_sponsor(article, issue_date):
    """Issue date already denotes America/Denver, not the execution UTC date."""
    day = date.fromisoformat(str(issue_date))
    panels = article.select('.brandx-sponsor')
    required = day >= START and day.weekday() == 0
    if not required:
        if panels or article.select('#brandx-revised-panel'):
            raise ValueError('Brand X sponsorship is only approved for Mondays from November 9')
        return None
    if len(panels) != 1:
        raise ValueError('Monday issue requires exactly one approved Brand X panel')
    panel = panels[0]
    if panel.name != 'section' or panel.attrs != {
            'class': ['brandx-sponsor'], 'data-sponsor': 'brandx',
            'data-sponsor-date': day.isoformat()}:
        raise ValueError('Invalid Brand X sponsor wrapper or date')
    sharing = article.select('section.growth-strip')
    if len(sharing) != 1 or panel.find_next_sibling() is not sharing[0]:
        raise ValueError('Brand X panel must immediately precede the sharing section')
    if 'Useful enough to pass along?' not in sharing[0].get_text(' ', strip=True):
        raise ValueError('Brand X panel requires the established sharing section')
    expected = BeautifulSoup(Path(__file__).with_name('brandx_panel.html').read_text(), 'html.parser')
    expected_nodes = tuple(v for child in expected.children if (v := _tree(child)) is not None)
    actual_nodes = tuple(v for child in panel.children if (v := _tree(child)) is not None)
    if actual_nodes != expected_nodes or len(article.select('#brandx-revised-panel')) != 1:
        raise ValueError('Brand X panel differs from the approved design, assets or copy')
    return panel


def sponsor_plain(panel):
    lines = [' '.join(node.get_text(' ', strip=True).split())
             for node in panel.find_all(['p', 'h2'])]
    lines.extend(' '.join(a.get_text(' ', strip=True).split()) + ': ' + a['href']
                 for a in panel.find_all('a', href=True))
    return lines
