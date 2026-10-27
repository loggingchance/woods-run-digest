import sys
import tempfile
import unittest
import base64
import io
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import render_daily_reel as reel

class ReelTests(unittest.TestCase):
    def test_approved_timing(self):
        self.assertEqual(sum(reel.DURATIONS),41.5)
        self.assertEqual(reel.FPS,30)
        self.assertEqual(reel.segment_frame_counts(), [75,210,210,210,210,210,120])
        self.assertEqual(sum(reel.segment_frame_counts()) / reel.FPS, 41.5)
        self.assertEqual((reel.W,reel.H),(1080,1920))

    def test_resource_is_an_extra_segment_before_closing(self):
        for count in (4, 5):
            with self.subTest(stories=count):
                before = reel.segment_frame_counts(count)
                after = reel.segment_frame_counts(count, has_resource=True)
                self.assertEqual(after, before[:-1] + [300, before[-1]])
                self.assertEqual(sum(after) / reel.FPS, 44.5 if count == 4 else 51.5)

    def test_resource_layout_with_long_title_and_description(self):
        resource = dict(title='A practical field reference for forest managers, landowners and logging businesses working across North America',
                        description=('This reference app brings forestry tables and calculations together for field use, with tree scale, log scale, prism cruising and stocking-guide references. ' * 3).strip(),
                        url='https://example.org/resources/a-long-resource-link?edition=2026-10-27')
        frame = reel.resource_frame(resource)
        self.assertEqual(frame.size, (1080, 1920))

    def test_resource_never_silently_clips_unbroken_text(self):
        with self.assertRaises(ValueError):
            reel.resource_frame(dict(title='W'*100, description='Useful app.', url='https://example.org/'))

    def test_selection_and_missing_art_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); page=root/'2026/10/12/index.html';page.parent.mkdir(parents=True)
            story='<article class="story"><p class="region-label">WEST</p><h3>Timber sales</h3><p>Body.</p></article>'
            page.write_text('<section class="issue-section special-opportunity">'+story+'</section><section class="issue-section">'+story*6+'</section>')
            selected=reel.read_stories(root,'2026-10-12')
            self.assertEqual(len(selected),5)
            with self.assertRaises(ValueError):reel.illustration(dict(selected[0],image='/assets/missing.png'),root)
            page.write_text('<section class="issue-section">'+story*4+'</section>')
            selected = reel.read_stories(root,'2026-10-12')
            self.assertEqual(len(selected), 4)
            self.assertEqual(reel.segment_frame_counts(len(selected)), [75,210,210,210,210,120])
            page.write_text('<section class="issue-section"></section>')
            with self.assertRaises(ValueError):
                reel.read_stories(root,'2026-10-12')

    def test_story_subject_changes_illustration(self):
        a=reel.illustration(dict(headline='Timber sales',body='',image=None),Path('.'))
        b=reel.illustration(dict(headline='Equipment investment',body='',image=None),Path('.'))
        c=reel.illustration(dict(headline='Application deadline',body='',image=None),Path('.'))
        e=reel.illustration(dict(headline='Bid opening',body='',image=None),Path('.'))
        # Both an application deadline and a bid opening intentionally select
        # the same approved bids illustration; unrelated topics remain distinct.
        self.assertEqual(c.tobytes(), e.tobytes())
        self.assertEqual(len({im.tobytes() for im in [a,b,c]}),3)


    def test_weekday_opener_rotation_and_monday_fallback(self):
        self.assertNotIn('Monday', reel.WEEKDAY_COVERS)
        self.assertEqual(reel.WEEKDAY_COVERS['Tuesday'], 'tuesday.jpg.b64')
        self.assertEqual(reel.WEEKDAY_COVERS['Wednesday'], 'wednesday.jpg.b64')
        self.assertEqual(reel.WEEKDAY_COVERS['Thursday'], 'thursday.jpg.b64')
        self.assertEqual(reel.WEEKDAY_COVERS['Friday'], 'friday.jpg.b64')
        self.assertEqual(reel.WEEKDAY_COVERS['Saturday'], 'saturday.jpg.b64')
        self.assertEqual(reel.WEEKDAY_COVERS['Sunday'], 'sunday.jpg.b64')
        original = reel.BRAND
        try:
            with tempfile.TemporaryDirectory() as td:
                brand = Path(td)
                (brand / 'weekday').mkdir()
                Image.new('RGB', (12, 12), (20, 40, 60)).save(brand / 'forester.webp', 'WEBP')
                buf = io.BytesIO()
                Image.new('RGB', (12, 12), (180, 120, 60)).save(buf, 'JPEG')
                (brand / 'weekday' / 'tuesday.jpg.b64').write_text(
                    base64.b64encode(buf.getvalue()).decode('ascii')
                )
                reel.BRAND = brand
                monday = reel.opener_art('2026-10-19')
                tuesday = reel.opener_art('2026-10-20')
                self.assertEqual(monday.size, (12, 12))
                self.assertEqual(tuesday.size, (12, 12))
                self.assertNotEqual(monday.getpixel((5,5)), tuesday.getpixel((5,5)))
                wednesday = reel.opener_art('2026-10-21')
                self.assertEqual(wednesday.getpixel((5,5)), monday.getpixel((5,5)))
        finally:
            reel.BRAND = original

