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
    def test_internal_urls(self):
        self.assertEqual(normalize_url('/subscribe/'),'https://woods-run-digest.steve760060.chatgpt.site/subscribe/')
    def test_legacy_root_rewrite(self):
        self.assertEqual(normalize_url('https://woodsrun.forestenterprise.org/2026/10/08/'),'https://woods-run-digest.steve760060.chatgpt.site/2026/10/08/')
    def test_token_rejected(self):
        with self.assertRaises(ValueError):normalize_url('https://unsubscribe.resend.com/?token=secret')
    def test_javascript_rejected(self):
        with self.assertRaises(ValueError):normalize_url('javascript:alert(1)')
    def test_stale_content_rejected(self):
        with self.assertRaises(ValueError):compile_payload(self.page(),self.issue('2026-10-09'))
    def test_active_content_rejected(self):
        with self.assertRaises(ValueError):compile_payload(self.page().replace('Full source paragraph.','<script>alert(1)</script>Text'),self.issue())

if __name__=='__main__':unittest.main()
