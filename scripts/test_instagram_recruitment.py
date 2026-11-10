import sys,types,unittest
from pathlib import Path
sys.modules['buffer_queue']=types.SimpleNamespace()
sys.path.insert(0,str(Path(__file__).parent))
import instagram_recruitment as c
class Validation(unittest.TestCase):
    def item(self):return {'slot':'2026-11-03','asset':'assets/instagram-recruitment/test.jpg','sha256':'a'*64,'caption':'The Woods Run Digest. Subscribe free — link in bio.'}
    def test_schedule_dst(self):
        due=c.check_item(self.item());self.assertEqual(due.isoformat(),'2026-11-03T08:00:00-07:00')
    def test_wrong_day(self):
        i=self.item();i['slot']='2026-11-04'
        with self.assertRaises(AssertionError):c.check_item(i)
    def test_wrong_asset(self):
        i=self.item();i['asset']='assets/videos/test.jpg'
        with self.assertRaises(AssertionError):c.check_item(i)
    def test_wrong_caption(self):
        i=self.item();i['caption']='Bad branding'
        with self.assertRaises(AssertionError):c.check_item(i)
    def fact_item(self):
        i=self.item()
        i.update(campaign='facts',slot='2026-11-11',fact='A source-verified forestry fact.',source_issue='https://woodsrun.forestenterprise.org/2026/11/10/',source_url='https://example.org/source')
        i['caption']+=' '+i['fact']
        return i
    def test_fact_wednesday(self):
        self.assertEqual(c.check_item(self.fact_item()).isoformat(),'2026-11-11T08:00:00-07:00')
    def test_fact_friday(self):
        i=self.fact_item();i['slot']='2026-11-13'
        self.assertEqual(c.check_item(i).isoformat(),'2026-11-13T08:00:00-07:00')
    def test_fact_dst(self):
        i=self.fact_item();i['slot']='2027-07-07'
        self.assertEqual(c.check_item(i).isoformat(),'2027-07-07T08:00:00-06:00')
    def test_fact_cannot_use_generic_day(self):
        i=self.fact_item();i['slot']='2026-11-12'
        with self.assertRaises(AssertionError):c.check_item(i)
    def test_fact_requires_sources_and_exact_caption(self):
        for field in ('source_issue','source_url','fact'):
            i=self.fact_item();i.pop(field)
            with self.assertRaises(AssertionError):c.check_item(i)
        i=self.fact_item();i['caption']=self.item()['caption']
        with self.assertRaises(AssertionError):c.check_item(i)
    def test_fact_cannot_be_immediate(self):
        i=self.fact_item();i['immediate']=True
        with self.assertRaises(AssertionError):c.check_item(i)
    def test_unknown_campaign(self):
        i=self.item();i['campaign']='other'
        with self.assertRaises(AssertionError):c.check_item(i)
if __name__=='__main__':unittest.main()

