import copy
import datetime
import sys
import json
import tempfile
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import daily_resources as r
from book_rotation import featured_item
from prepare_email_payload import compile_payload
from sync_public_editorial import validate, sync


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.urls = ['https://a.example/', 'https://b.example/', 'https://c.example/']
        self.catalog = {url: dict(title='Tool '+str(i), kind='website',
            description='Provides verified planning guidance.', source_url=url, verified=True)
            for i, url in enumerate(self.urls)}

    def snapshot(self, urls=None):
        return r.refresh([['Links', 'Notes']] + [[u, 'source data'] for u in
                         (self.urls if urls is None else urls)], checked_at='2026-10-24')

    def publish(self, day, snapshot, state):
        choice, state = r.prepare(day, snapshot, self.catalog, state)
        issue = dict(date=day, featuredResource=r.public_selection(choice))
        return choice, r.confirm_publication(day, issue, state)

    def test_cycle_additions_deletions_reorder_duplicates_and_reset(self):
        a, state = self.publish('2026-10-25', self.snapshot(self.urls[:2]), {})
        self.assertEqual(a['item']['url'], self.urls[0])
        reordered = self.snapshot([self.urls[1], self.urls[0], self.urls[1], self.urls[2]])
        self.assertEqual(len(reordered['entries']), 3)
        b, state = self.publish('2026-10-26', reordered, state)
        self.assertEqual(b['item']['url'], self.urls[1])
        c, state = self.publish('2026-10-27', self.snapshot([self.urls[2]]), state)
        self.assertEqual(c['item']['url'], self.urls[2])
        again, state = self.publish('2026-10-28', self.snapshot(), state)
        self.assertEqual(again['item']['url'], self.urls[0])
        self.assertEqual(state['cycle'], 2)

    def test_notes_and_row_changes_do_not_reset(self):
        _, state = self.publish('2026-10-25', self.snapshot(), {})
        snapshot = r.refresh([['Links','Notes'], [self.urls[0], 'changed'],
                             [self.urls[1]], [self.urls[2]]], checked_at='later')
        choice, _ = r.prepare('2026-10-26', snapshot, self.catalog, state)
        self.assertEqual(choice['item']['url'], self.urls[1])

    def test_outage_uses_cache_empty_read_does_not(self):
        cached = r.refresh(None, self.snapshot(), checked_at='later', error='temporary outage')
        choice, _ = r.prepare('2026-10-25', cached, self.catalog, {})
        self.assertTrue(choice['cached'])
        self.assertIsNotNone(choice['item'])
        empty = self.snapshot([])
        choice, state = self.publish('2026-10-25', empty, {})
        self.assertIsNone(choice['item'])
        self.assertEqual(state.get('used', []), [])
        missing = r.refresh(None, checked_at='now', error='no cache')
        self.assertIsNone(r.prepare('2026-10-26', missing, self.catalog, {})[0]['item'])

    def test_draft_not_consumed_idempotence_and_uncertain_reconciliation(self):
        choice, state = r.prepare('2026-10-25', self.snapshot(), self.catalog, {})
        self.assertNotIn('used', state)
        repeated, _ = r.prepare('2026-10-25', self.snapshot([]), {}, state)
        self.assertEqual(choice, repeated)
        issue = dict(date='2026-10-25', featuredResource=r.public_selection(choice))
        published = r.confirm_publication('2026-10-25', issue, state)
        self.assertEqual(published, r.confirm_publication('2026-10-25', issue, published))
        bad = copy.deepcopy(issue); bad['featuredResource']['item']['description'] = 'changed'
        with self.assertRaises(ValueError): r.confirm_publication('2026-10-25', bad, state)
        self.assertNotIn('used', state)

    def test_invalid_unverified_and_stable_identity(self):
        self.assertEqual(r.identity('HTTPS://A.EXAMPLE:443/#fragment'), self.urls[0])
        snapshot = self.snapshot(['javascript:alert(1)', self.urls[0], self.urls[0]+'#fragment'])
        self.assertEqual(len(snapshot['entries']), 1)
        self.assertEqual(r.eligible(snapshot, {}), {})
        with self.assertRaises(ValueError): r.refresh([['Wrong']], checked_at='now')

    def fixture(self, day='2026-10-25', empty=False):
        selection, _ = r.prepare(day, self.snapshot([] if empty else None), self.catalog, {})
        dt = datetime.date.fromisoformat(day)
        display = dt.strftime('%B') + f' {dt.day}, {dt.year}'
        issue = dict(date=day, displayDate=display, url='/'+day.replace('-','/')+'/',
            summary='summary',socialText='social',cardTeaser='teaser',cardSubhead='context',
            strikingText='observation',featuredResource=r.public_selection(selection))
        page = '<article class="edition-wrap"><h1>'+display+'</h1><h2>Action Detector</h2>'
        page += ''.join('<article class="story"><h3>Story</h3><p>Facts.</p><p>Context.</p><p>Source.</p></article>' for _ in range(4))
        page += '<h2>Under the Radar</h2>' + r.resource_html(selection) + '</article>'
        return page, issue

    def test_web_and_complete_email_same_resource_thursday_without_feature(self):
        for day in ('2026-10-25', '2026-10-29'):
            page, issue = self.fixture(day)
            validate(page, issue)
            payload = compile_payload(page, issue)
            item = issue['featuredResource']['item']
            self.assertEqual(payload['featured_item'], item)
            self.assertEqual(payload['html'].count(item['url']), 1)
            self.assertIn(item['description'], payload['text'])
            self.assertIn('website:', payload['text'])
            self.assertNotIn('Woods-Ready Safety Plan', payload['text'])
            self.assertNotIn('spreadsheet_id', str(issue['featuredResource']))
            with self.assertRaises(ValueError): compile_payload(page, dict(issue, featuredResource=None))
            with self.assertRaises(ValueError): validate(page.replace(item['description'], 'different'), issue)

    def test_empty_notice_is_preserved_without_fallback(self):
        page, issue = self.fixture(empty=True)
        validate(page, issue)
        payload = compile_payload(page, issue)
        self.assertIsNone(payload['featured_item'])
        self.assertIn('No featured resource is available', payload['text'])

    def test_historical_behavior_immutable(self):
        self.assertEqual(featured_item('2026-10-24')['title'], 'Wet Woods')
        with self.assertRaises(ValueError): featured_item('2026-10-25')
        with self.assertRaises(ValueError): r.prepare('2026-10-24', self.snapshot(), self.catalog, {})
        choice, state = self.publish('2026-10-26', self.snapshot(), {})
        before = copy.deepcopy(state)
        with self.assertRaises(ValueError): r.prepare('2026-10-25', self.snapshot(), self.catalog, state)
        self.assertEqual(before, state)

    def test_mirror_preserves_history_and_atomic_private_state(self):
        page, issue = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = {'date': '2026-10-24', 'summary': 'Historical content'}
            r.save_private(root/'data/issues.json', [old])
            historical = root/'2026/10/24/index.html'
            historical.parent.mkdir(parents=True)
            historical.write_text('Original historical page')
            sync(root, [issue], {issue['url']+'index.html': page}, issue['date'])
            self.assertEqual(json.loads((root/'data/issues.json').read_text()), [issue, old])
            self.assertEqual(historical.read_text(), 'Original historical page')
            self.assertEqual((root/'2026/10/25/index.html').read_text(), page)

    def test_failed_draft_can_be_skipped_without_consumption(self):
        draft, state = r.prepare('2026-10-25', self.snapshot(), self.catalog, {})
        later, state = self.publish('2026-10-26', self.snapshot(), state)
        self.assertEqual(draft['item'], later['item'])
        self.assertEqual(len(state['used']), 1)
        with self.assertRaises(ValueError):
            r.confirm_publication('2026-10-25', dict(date='2026-10-25',
                featuredResource=r.public_selection(draft)), state)


if __name__ == '__main__': unittest.main()
