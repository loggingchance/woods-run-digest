import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_public_editorial import sync, validate
from generate_social_cards import add_artwork
import generate_social_cards
from PIL import Image


class EditorialHandoffTests(unittest.TestCase):
    def setUp(self):
        # A compact canonical fixture with required article structure.
        self.issue = {'date': '2026-10-10', 'displayDate': 'October 10, 2026',
                      'url': '/2026/10/10/', 'summary': 'summary', 'socialText': 'social',
                      'cardTeaser': 'teaser', 'cardSubhead': 'subhead', 'strikingText': 'observation'}
        self.page = '<article class="edition-wrap"><h1>October 10, 2026</h1>' + ''.join(
            '<h2>' + h + '</h2>' for h in ['By the Numbers', 'Action Detector', 'Under the Radar', 'Forest Business School']) + ''.join(
            '<article class="story"><h3>Headline</h3><p>Paragraph with <a href="https://example.org/source">original source</a>.</p></article>' for _ in range(12)) + '</article>'

    def test_rejects_yesterdays_metadata_before_any_write(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(ValueError):
                sync(root, [self.issue], {}, '2026-10-11')
            self.assertEqual(list(root.iterdir()), [])

    def test_mirrors_exact_article_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / 'data').mkdir()
            (root / 'data/issues.json').write_text(json.dumps([{'date': '2026-10-09'}, {'date': '2026-10-10', 'summary': 'wrong'}]))
            sync(root, [self.issue], {'/2026/10/10/index.html': self.page}, '2026-10-10')
            self.assertEqual((root / '2026/10/10/index.html').read_text(), self.page)
            self.assertEqual(json.loads((root / 'data/issues.json').read_text()), [self.issue, {'date': '2026-10-09'}])

    def test_rejects_incomplete_or_wrong_date_page(self):
        for page in [self.page.replace('October 10, 2026', 'October 9, 2026'), self.page.replace('Action Detector', 'Missing')]:
            with self.assertRaises(ValueError): validate(page, self.issue)

    def test_new_format_allows_no_redundant_top_recap(self):
        issue = {'date': '2026-10-15', 'displayDate': 'October 15, 2026',
                 'url': '/2026/10/15/', 'summary': 'summary', 'socialText': 'social',
                 'cardTeaser': 'teaser', 'cardSubhead': 'subhead', 'strikingText': 'observation'}
        page = '<article class="edition-wrap"><h1>October 15, 2026</h1><h2>Action Detector</h2>' + ''.join(
            '<article class="story"><h3>Headline</h3><p>Paragraph with <a href="https://example.org/source'+str(i)+'">source</a>.</p></article>' for i in range(6)
        ) + '<h2>Under the Radar</h2><article class="story"><h3>Under</h3><p>Useful detail.</p></article>' +             '<section class="wet-woods-box"><p class="section-kicker">BOOKS &amp; APPS</p><h2>Timber Tempo</h2><p>Useful two-sentence description.</p><p><a href="https://www.amazon.com/dp/B0DRYY34KW">Explore</a></p></section></article>'
        validate(page, issue)

    def test_new_format_rejects_repeated_by_the_numbers_sources(self):
        issue = {'date': '2026-10-15', 'displayDate': 'October 15, 2026',
                 'url': '/2026/10/15/', 'summary': 'summary', 'socialText': 'social',
                 'cardTeaser': 'teaser', 'cardSubhead': 'subhead', 'strikingText': 'observation'}
        page = '<article class="edition-wrap"><h1>October 15, 2026</h1>' +             '<section><h2>By the Numbers</h2><p>42 units <a href="https://example.org/repeated">source</a></p></section>' +             '<h2>Action Detector</h2>' + ''.join(
                '<article class="story"><h3>Headline</h3><p>Story <a href="'+('https://example.org/repeated' if i == 0 else 'https://example.org/source'+str(i))+'">source</a>.</p></article>' for i in range(6)
            ) + '<h2>Under the Radar</h2><article class="story"><h3>Under</h3><p>Useful detail.</p></article>' +             '<section class="wet-woods-box"><p class="section-kicker">BOOKS &amp; APPS</p><h2>Timber Tempo</h2><p>Useful description.</p></section></article>'
        with self.assertRaises(ValueError):
            validate(page, issue)

    def test_missing_official_artwork_is_fatal(self):
        original = generate_social_cards.ART_FILE
        try:
            generate_social_cards.ART_FILE = Path('/nonexistent-official-woodsrun-artwork.webp')
            with self.assertRaises(FileNotFoundError):
                add_artwork(Image.new('RGBA', (1200, 630)), 'Saturday')
        finally:
            generate_social_cards.ART_FILE = original


if __name__ == '__main__': unittest.main()
