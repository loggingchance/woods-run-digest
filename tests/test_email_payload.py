import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_email_payload import compile_payload, normalize_url

class EmailTests(unittest.TestCase):
    def issue(self,date='2026-10-08'):
        return {'date':date,'displayDate':'October 8, 2026' if date.endswith('08') else 'October 9, 2026','url':'/'+date.replace('-','/')+'/'}
    def page(self,display='October 8, 2026'):
        return '<article class="edition-wrap"><h1>'+display+'</h1><h2>By the numbers</h2><p>Full source paragraph.</p><h2>Action Detector</h2><p>Full story <a href="https://example.org/source?detail=full">Source</a></p><p>Another full paragraph</p><nav><a href="/archive/">Archive</a></nav></article>'
    def test_complete_content(self):
        p=compile_payload(self.page(),self.issue())
        self.assertIn('Full source paragraph.',p['text'])
        self.assertIn('https://example.org/source?detail=full',p['text'])
        self.assertEqual(p['featured_book']['title'],'After Wood')
        self.assertIn('{{{RESEND_UNSUBSCRIBE_URL}}}',p['html'])
        self.assertNotIn('{{{RESEND_UNSUBSCRIBE_URL}}}',p['owner_test_html'])
    def test_rotation_next_day(self):
        p=compile_payload(self.page('October 9, 2026'),self.issue('2026-10-09'))
        self.assertEqual(p['featured_book']['title'],'Wet Woods')
    def test_added_book_without_duplicate_fallback(self):
        from book_rotation import book_html
        issue={'date':'2026-10-13','displayDate':'October 13, 2026','url':'/2026/10/13/'}
        page=self.page(issue['displayDate']).replace('</article>',book_html(issue['date'])+'</article>')
        payload=compile_payload(page,issue)
        self.assertEqual(payload['featured_book']['title'],'Continuous Improvement in Logging')
        self.assertEqual(payload['html'].count('https://cinl.loggingchance.com/'),1)
        self.assertIn('Jeffrey G. Benjamin',payload['text'])
        self.assertNotIn('View Timber Tempo on Amazon',payload['html'])
    def test_books_and_apps_rotation(self):
        from book_rotation import featured_item, item_html
        self.assertEqual(featured_item('2026-10-14')['title'],'Wet Woods')
        self.assertEqual(featured_item('2026-10-15')['title'],'Timber Tempo')
        self.assertEqual(featured_item('2026-10-16')['title'],'After Wood')
        self.assertEqual(featured_item('2026-10-17')['title'],'Continuous Improvement in Logging')
        self.assertEqual(featured_item('2026-10-18')['title'],'Woods-Ready Safety Plan')
        issue={'date':'2026-10-18','displayDate':'October 18, 2026','url':'/2026/10/18/'}
        page=self.page(issue['displayDate']).replace('</article>',item_html(issue['date'])+'</article>')
        payload=compile_payload(page,issue)
        self.assertEqual(payload['featured_item']['kind'],'app')
        self.assertEqual(payload['featured_item']['title'],'Woods-Ready Safety Plan')
        self.assertIn('logging crews assemble coordinates',payload['text'])
        self.assertEqual(payload['html'].count('https://wrsp.lumbermen.org/'),1)
    def test_linked_image_preserved(self):
        page=self.page().replace('<p>Full source paragraph.</p>','<figure><a href="/assets/memorial.png"><img src="/assets/memorial.png" alt="Memorial portrait"></a></figure><p>Full source paragraph.</p>')
        p=compile_payload(page,self.issue())
        url='https://woodsrun.forestenterprise.org/assets/memorial.png'
        self.assertIn(f'<img src="{url}" alt="Memorial portrait"',p['html'])
        self.assertIn(url,p['all_urls'])
        self.assertTrue(p['links_preserved'])
    def test_internal_urls(self):
        self.assertEqual(normalize_url('/subscribe/'),'https://woodsrun.forestenterprise.org/subscribe/')
    def test_legacy_root_rewrite(self):
        self.assertEqual(normalize_url('https://woods-run-digest.steve760060.chatgpt.site/2026/10/08/'),'https://woodsrun.forestenterprise.org/2026/10/08/')
    def test_token_rejected(self):
        with self.assertRaises(ValueError):normalize_url('https://unsubscribe.resend.com/?token=secret')
    def test_javascript_rejected(self):
        with self.assertRaises(ValueError):normalize_url('javascript:alert(1)')
    def test_stale_content_rejected(self):
        with self.assertRaises(ValueError):compile_payload(self.page(),self.issue('2026-10-09'))
    def test_active_content_rejected(self):
        with self.assertRaises(ValueError):compile_payload(self.page().replace('Full source paragraph.','<script>alert(1)</script>Text'),self.issue())

if __name__=='__main__':unittest.main()
