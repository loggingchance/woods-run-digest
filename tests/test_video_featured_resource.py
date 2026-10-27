import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from video_featured_resource import HEADING, read_featured_resource
from post_to_buffer import compose_instagram_post, compose_youtube_post, compose_x_post


class VideoFeaturedResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.date = '2026-10-27'
        self.issue = dict(date=self.date, displayDate='October 27, 2026',
                          url='/2026/10/27/', summary='The news summary.',
                          featuredResource=dict(date=self.date, item=dict(
                              title='Forester’s Fieldbook', kind='app',
                              description='app: Forester’s Fieldbook is a field reference app.',
                              url='https://burl.lumbermen.org/')))

    def html(self, content=None):
        page = self.root / '2026/10/27/index.html'
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(content or '''<section class="wet-woods-box">
          <p class="section-kicker">Today's Featured Resources</p>
          <h2>Forester's Fieldbook</h2><p>app: Forester's Fieldbook is a reference app.</p>
          <p><a class="book-button" href="https://burl.lumbermen.org/">Explore →</a></p>
          </section>''')

    def test_metadata_and_normalization(self):
        item = read_featured_resource(self.root, self.date, self.issue)
        self.assertEqual(item['title'], 'The Forester’s Fieldbook')
        self.assertEqual(item['description'], 'The Forester’s Fieldbook is a field reference app.')
        self.assertEqual(self.issue['featuredResource']['item']['title'], 'Forester’s Fieldbook')

    def test_load_matching_date_not_latest(self):
        (self.root / 'data').mkdir()
        other = copy.deepcopy(self.issue)
        other['date'] = '2026-10-28'
        other['featuredResource']['item']['title'] = 'Wrong day'
        (self.root / 'data/issues.json').write_text(json.dumps([other, self.issue]))
        self.assertEqual(read_featured_resource(self.root, self.date)['title'], 'The Forester’s Fieldbook')

    def test_html_fallback_only_for_missing_key(self):
        self.html()
        issue = dict(date=self.date)
        self.assertEqual(read_featured_resource(self.root, self.date, issue)['title'], 'The Forester’s Fieldbook')
        issue['featuredResource'] = dict(date=self.date, item=None)
        self.assertIsNone(read_featured_resource(self.root, self.date, issue))
        issue['featuredResource'] = None
        self.assertIsNone(read_featured_resource(self.root, self.date, issue))

    def test_metadata_wins_over_html(self):
        self.html()
        self.issue['featuredResource']['item']['title'] = 'Canonical selection'
        self.assertEqual(read_featured_resource(self.root, self.date, self.issue)['title'], 'Canonical selection')

    def test_wrong_date_rejected(self):
        self.issue['featuredResource']['date'] = '2026-10-26'
        with self.assertRaisesRegex(ValueError, 'date mismatch'):
            read_featured_resource(self.root, self.date, self.issue)
        with self.assertRaises(ValueError):
            read_featured_resource(self.root, '../2026-10-27', self.issue)

    def test_unsafe_or_incomplete_metadata_never_falls_back(self):
        self.html()
        for url in ('javascript:alert(1)', 'https://user:secret@example.org/', 'https://example.org/a\nb', ''):
            with self.subTest(url=url):
                self.issue['featuredResource']['item']['url'] = url
                with self.assertRaises(ValueError):
                    read_featured_resource(self.root, self.date, self.issue)

    def test_unavailable_or_absent_html(self):
        self.assertIsNone(read_featured_resource(self.root, self.date, {}))
        self.html('''<section class="wet-woods-box"><p class="section-kicker">Today's Featured Resource</p><p>No resource available today.</p></section>''')
        self.assertIsNone(read_featured_resource(self.root, self.date, {}))

    def test_caption_title_url_and_x_unchanged(self):
        original = copy.deepcopy(self.issue)
        del original['featuredResource']
        for caption in (compose_instagram_post(self.issue),
                        compose_youtube_post(self.issue, 'https://example.org/edition')):
            self.assertIn(HEADING + '\nThe Forester’s Fieldbook\nhttps://burl.lumbermen.org/', caption)
            self.assertNotIn('app:', caption)
        self.assertEqual(compose_x_post(self.issue, 'https://example.org/edition'),
                         compose_x_post(original, 'https://example.org/edition'))

    def test_long_resource_caption_preserves_full_title_and_link(self):
        item = self.issue['featuredResource']['item']
        item['title'] = 'A practical reference for forest management and wood products business decisions ' * 3
        item['url'] = 'https://example.org/resources/' + 'long-resource-name-' * 8
        for caption in (compose_instagram_post(self.issue), compose_youtube_post(self.issue, 'https://example.org/edition')):
            self.assertIn(item['title'].strip(), caption)
            self.assertIn(item['url'], caption)


if __name__ == '__main__':
    unittest.main()
