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
if __name__=='__main__':unittest.main()
