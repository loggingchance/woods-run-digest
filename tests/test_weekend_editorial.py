import datetime,json,tempfile,sys,unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from market_table import validate_market_table
from prepare_striking_request import prepare
class WeekendEditorialTests(unittest.TestCase):
 def test_weekend_market_omitted(self):
  validate_market_table(BeautifulSoup('<article>News</article>','html.parser'),'2026-11-07')
  with self.assertRaises(ValueError):
   validate_market_table(BeautifulSoup('<section class="by-the-numbers"></section>','html.parser'),'2026-11-08')
 def test_weekday_still_requires_market(self):
  with self.assertRaises(ValueError):validate_market_table(BeautifulSoup('<article>News</article>','html.parser'),'2026-11-06')
 def test_unapproved_weekend_skips_handoff(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data').mkdir()
   (root/'data/issues.json').write_text(json.dumps([{'date':'2026-11-07','strikingSkip':True}]))
   self.assertFalse(prepare(root,datetime.datetime(2026,11,7,15,tzinfo=datetime.timezone.utc)))
   self.assertFalse((root/'data/striking-trigger.json').exists())
 def test_unrelated_weekend_striking_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data').mkdir()
   (root/'data/issues.json').write_text(json.dumps([{'date':'2026-11-07','strikingText':'Unrelated','weekendFeatureStatus':'approved','strikingSource':'weekend_feature','weekendFeature':{'kind':'profile','striking_text':'Approved'}}]))
   with self.assertRaisesRegex(ValueError,'approved canonical feature'):prepare(root,datetime.datetime(2026,11,7,15,tzinfo=datetime.timezone.utc))
if __name__=='__main__':unittest.main()
