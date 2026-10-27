"""Local QR/layout checks; opt-in encoded-video QA needs requirements-qa.txt."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import render_daily_reel as reel

URLS = ['https://burl.lumbermen.org/',
        'https://example.org/resources/' + 'field-reference-' * 14 + '?edition=2026-10-28&format=app#tables']

class ResourceQRTests(unittest.TestCase):
    def test_black_white_quiet_zone_and_integer_modules(self):
        for url in URLS:
            qr = reel.resource_qr(url)
            self.assertLessEqual(qr.width, 480)
            self.assertEqual(set(qr.getdata()), {(0, 0, 0), (255, 255, 255)})
            # At least four modules of white surround every edge (>=3 px/module).
            for box in [(0, 0, qr.width, 12), (0, qr.height-12, qr.width, qr.height),
                        (0, 0, 12, qr.height), (qr.width-12, 0, qr.width, qr.height)]:
                self.assertEqual(set(qr.crop(box).getdata()), {(255, 255, 255)})

    def test_display_label_never_changes_encoded_destination(self):
        self.assertEqual(reel.resource_display_url(URLS[0]), 'burl.lumbermen.org')
        self.assertEqual(reel.resource_display_url(URLS[1]), 'example.org/…')
        self.assertEqual(reel.resource_display_url('https://example.org/book'), 'example.org/book')
        label = reel.resource_display_url('https://' + 'a'*63 + '.example.org/long')
        self.assertLessEqual(len(label), 48)

    @unittest.skipUnless(os.environ.get('QR_VIDEO_QA') == '1', 'opt-in actual MP4 decoding QA')
    def test_encoded_four_and_five_story_videos(self):
        import zxingcpp
        destination = Path(os.environ['QR_QA_DIR'] if 'QR_QA_DIR' in os.environ else
                           tempfile.mkdtemp(prefix='resource-qr-qa-'))
        destination.mkdir(parents=True, exist_ok=True)
        results = []
        for count, url in zip((4, 5), URLS):
            resource = dict(title='The Forester’s Fieldbook' if count == 4 else
                            'A practical field reference for forest managers, landowners and logging businesses working across North America',
                            description='This reference app brings forestry tables and calculations together for field use, with tree scale, log scale, prism cruising and stocking-guide references.', url=url)
            stories = [dict(headline='Timber sales and working forests', body='A concise verified forestry news summary.', region='NORTH AMERICA', image=None)] * count
            output = destination / f'{count}-stories.mp4'
            with patch.object(reel, 'read_stories', return_value=stories), patch.object(reel, 'read_featured_resource', return_value=resource):
                reel.render(reel.ROOT, '2026-10-28', 'October 28, 2026', output, destination / f'frames-{count}')
            probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(output)]))
            self.assertEqual([s['codec_type'] for s in probe['streams']], ['video'])
            self.assertEqual(float(probe['format']['duration']), 44.5 if count == 4 else 51.5)
            self.assertEqual(probe['streams'][0]['r_frame_rate'], '30/1')
            # Decode the first, middle and final QR frames from the actual H.264 MP4.
            for offset in (0, 5, 9.9):
                timestamp = 2.5 + 7*count + offset
                frame = destination / f'{count}-encoded-{offset}.png'
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(timestamp), '-i', str(output), '-frames:v', '1', str(frame)], check=True)
                im = Image.open(frame).convert('RGB')
                for width in (1080, 540, 360):
                    scaled = im.resize((width, width*16//9), Image.Resampling.LANCZOS)
                    decoded = zxingcpp.read_barcodes(scaled)
                    self.assertEqual([r.text for r in decoded], [url], (count, offset, width))
                    scaled.save(destination / f'{count}-encoded-{offset}-{width}.png')
                    results.append(dict(stories=count, seconds=timestamp, width=width, decoded_url=url))
        (destination / 'decode-results.json').write_text(json.dumps(results, indent=2)+'\n')

if __name__ == '__main__':
    unittest.main()
