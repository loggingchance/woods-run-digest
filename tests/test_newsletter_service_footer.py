"""Regression coverage for the daily small newsletter-service footer; no sends."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prepare_email_payload as m

TEXT='Click here to setup a weekly custom email newsletter for your organization.'
URL='https://news.forestenterprise.org/'
FOOTER=f'<p class="newsletter-service-footer"><a href="{URL}">{TEXT}</a></p>'
PAGE='<html><body><main><article class="edition-wrap"><h1>November 15, 2026</h1><h2>News</h2><p>Story one.</p><p>Story two.</p><p>Story three.</p><p>Story four.</p></article>{footer}</main></body></html>'
RECORD={'date':'2026-11-15','displayDate':'November 15, 2026','url':'/2026/11/15/'}

class NewsletterFooterTests(unittest.TestCase):
 def compile(self,footer):
  with patch.object(m,'validate_feature',return_value=None),patch.object(m,'validate_market_table'):
   return m.compile_payload(PAGE.format(footer=footer),RECORD)
 def test_preserved_once_in_every_output(self):
  result=self.compile(FOOTER)
  for key in ('html','text','owner_test_html','owner_test_text'):
   self.assertEqual(result[key].count(TEXT),1)
   self.assertIn(URL,result[key])
  self.assertIn('font-size:13px',result['html'])
  self.assertIn(URL,result['all_urls'])
 def test_missing_source_is_not_invented(self):
  self.assertNotIn(TEXT,self.compile('')['html'])
 def test_duplicate_or_changed_destination_rejected(self):
  for footer in (FOOTER*2,FOOTER.replace(URL,'https://example.org/')):
   with self.assertRaises(ValueError):self.compile(footer)
if __name__=='__main__':unittest.main()
