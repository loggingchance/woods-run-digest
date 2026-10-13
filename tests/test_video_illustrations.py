import sys
import unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import video_illustration_library as art


class ApprovedVideoIllustrations(unittest.TestCase):
    def test_all_eight_are_present_and_transparent(self):
        self.assertEqual(len(art.ART_FILES), 8)
        for category,filename in art.ART_FILES.items():
            with self.subTest(category=category):
                path=ROOT/'assets/video-illustrations'/filename
                self.assertTrue(path.is_file(), path)
                with Image.open(path) as img:
                    self.assertEqual(img.size,(900,900))
                    self.assertIn('A',img.convert('RGBA').getbands())
                    self.assertLess(img.convert('RGBA').getchannel('A').getextrema()[0],255)
                self.assertEqual(art.illustration_asset({'headline':category.replace('_',' ')},ROOT).parent,path.parent)

    def test_headline_priority_and_categories(self):
        for headline,expected in [
            ('Montana timber bids close Tuesday','bids'),
            ('Feller-buncher operating costs','feller_buncher'),
            ('Log trucks face new hauling rules','log_truck'),
            ('Wood pellet biomass boiler','biomass'),
            ('Sawmill closes two shifts','sawmill'),
            ('Conservation forest management plan','forest_planning'),
            ('New forestry research report','research'),
            ('Sawlogs and timber sales','logs')]:
            with self.subTest(headline=headline):
                self.assertEqual(art.choose_topic({'headline':headline,'body':'Timber sale research mentioned'}),expected)

    def test_render_is_1080_x_480_and_subject_varies(self):
        imgs=[art.topic_illustration({'headline':h},ROOT,(1080,480))
              for h in ('Log sales','Feller-buncher purchase','Grant deadline','Sawmill closure')]
        self.assertTrue(all(im.size==(1080,480) and im.mode=='RGB' for im in imgs))
        self.assertEqual(len({im.tobytes() for im in imgs}),4)


if __name__=='__main__': unittest.main()
