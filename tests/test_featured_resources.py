import datetime
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from book_rotation import ITEMS, featured_item, item_html, resource_heading
from prepare_email_payload import compile_payload
from sync_public_editorial import validate


class FeaturedResourcesTests(unittest.TestCase):
    def page_and_issue(self, day):
        date = datetime.date.fromisoformat(day)
        display = f'October {date.day}, 2026'
        issue = dict(date=day, displayDate=display, url='/'+day.replace('-', '/')+'/',
                     summary='summary', socialText='social', cardTeaser='teaser',
                     cardSubhead='subhead', strikingText='observation')
        page = '<article class="edition-wrap"><h1>'+display+'</h1><h2>Action Detector</h2>'
        page += ''.join('<article class="story"><h3>Story</h3><p>Facts.</p><p>Context.</p><p>Qualifications.</p></article>' for _ in range(4))
        return page+'<h2>Under the Radar</h2>'+item_html(day)+'</article>', issue

    def test_history_and_rotation_preserved(self):
        for offset in range(15):
            date = datetime.date(2026, 10, 14) + datetime.timedelta(days=offset)
            item = featured_item(date)
            expected = ITEMS[offset % 5]
            for key in ('kind', 'title', 'authors', 'url'):
                self.assertEqual(item[key], expected[key])
            if date < datetime.date(2026, 10, 25):
                self.assertEqual(item, expected)
                self.assertEqual(resource_heading(date), 'BOOKS & APPS')

    def test_future_labels_format_and_email_preservation(self):
        for day in range(25, 30):
            date = f'2026-10-{day}'
            page, issue = self.page_and_issue(date)
            item = featured_item(date)
            self.assertIn(item['kind'], item['description'].lower())
            self.assertEqual(BeautifulSoup(item_html(date), 'html.parser').select_one('.section-kicker').text, "Today's Featured Resources")
            validate(page, issue)
            payload = compile_payload(page, issue)
            self.assertIn("Today's Featured Resources", payload['text'])
            self.assertEqual(payload['html'].count(item['url']), 1)
            self.assertIn(item['description'], payload['text'])

    def test_future_fallback_and_validation(self):
        page, issue = self.page_and_issue('2026-10-25')
        payload = compile_payload(page.replace(item_html(issue['date']), ''), issue)
        self.assertIn("Today's Featured Resources", payload['text'])
        with self.assertRaises(ValueError):
            validate(page.replace('Today&#x27;s Featured Resources', 'BOOKS &amp; APPS'), issue)
        with self.assertRaises(ValueError):
            validate(page.replace('</article>', item_html(issue['date'])+'</article>', 1), issue)


if __name__ == '__main__':
    unittest.main()
