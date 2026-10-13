import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import render_daily_reel as reel

class ReelTests(unittest.TestCase):
    def test_approved_timing(self):
        self.assertEqual(sum(reel.DURATIONS),41.5)
        self.assertEqual(reel.FPS,30)
        self.assertEqual(reel.segment_frame_counts(), [75,210,210,210,210,210,120])
        self.assertEqual(sum(reel.segment_frame_counts()) / reel.FPS, 41.5)
        self.assertEqual((reel.W,reel.H),(1080,1920))

    def test_selection_and_missing_art_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); page=root/'2026/10/12/index.html';page.parent.mkdir(parents=True)
            story='<article class="story"><p class="region-label">WEST</p><h3>Timber sales</h3><p>Body.</p></article>'
            page.write_text('<section class="issue-section special-opportunity">'+story+'</section><section class="issue-section">'+story*6+'</section>')
            selected=reel.read_stories(root,'2026-10-12')
            self.assertEqual(len(selected),5)
            with self.assertRaises(ValueError):reel.illustration(dict(selected[0],image='/assets/missing.png'),root)
            page.write_text('<section class="issue-section">'+story*4+'</section>')
            with self.assertRaises(ValueError):reel.read_stories(root,'2026-10-12')

    def test_story_subject_changes_illustration(self):
        a=reel.illustration(dict(headline='Timber sales',body='',image=None),Path('.'))
        b=reel.illustration(dict(headline='Equipment investment',body='',image=None),Path('.'))
        c=reel.illustration(dict(headline='Application deadline',body='',image=None),Path('.'))
        e=reel.illustration(dict(headline='Bid opening',body='',image=None),Path('.'))
        # Both an application deadline and a bid opening intentionally select
        # the same approved bids illustration; unrelated topics remain distinct.
        self.assertEqual(c.tobytes(), e.tobytes())
        self.assertEqual(len({im.tobytes() for im in [a,b,c]}),3)
