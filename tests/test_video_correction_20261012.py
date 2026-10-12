import sys,unittest,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import correct_videos_20261012 as c

class VideoCorrection(unittest.TestCase):
    def test_disabled_needs_no_media(self):
        c.validate_request({'mode':'disabled'})
    def test_unpinned_media_rejected(self):
        with self.assertRaises(ValueError):c.validate_request({'mode':'audit','media_commit':'main'})
    def test_publish_requires_parent_confirmation(self):
        r={'mode':'publish','media_commit':'a'*40,'media_sha256':'b'*64,'format':'approved-v4','visual_review_confirmed':True,'activation':c.ACTIVATION}
        with self.assertRaisesRegex(ValueError,'parent confirmation'):c.validate_request(r)
    def test_duration(self):
        mvhd=b'\0'*12+struct.pack('>II',1000,41533)
        mvhd=struct.pack('>I4s',len(mvhd)+8,b'mvhd')+mvhd
        movie=struct.pack('>I4s',len(mvhd)+8,b'moov')+mvhd
        self.assertAlmostEqual(c.duration(movie),41.533)
    def test_unknown_attempt_blocks_retry(self):
        with self.assertRaisesRegex(ValueError,'unresolved'):c.choose_existing([],{'old_id':'old'},'url','text',{'attempt_started_at':'earlier'})
    def test_other_format_blocks(self):
        p={'id':'other','text':c.PAGE,'assets':[{'source':'old.mp4'}]}
        with self.assertRaises(ValueError):c.choose_existing([p],{'old_id':'old'},'new.mp4',c.PAGE,{})
    def test_existing_correct_reused(self):
        p={'id':'new','text':c.PAGE,'assets':[{'source':'new.mp4'}]}
        self.assertEqual(c.choose_existing([p],{'old_id':'old'},'new.mp4',c.PAGE,{}),p)
    def test_old_post_is_excluded(self):
        self.assertIsNone(c.choose_existing([{'id':'old','text':c.PAGE}],{'old_id':'old'},'new.mp4',c.PAGE,{}))
    def test_instagram_caption_unchanged(self):
        old={'provider_text':'Daily Digest '+c.PAGE}
        p=c.payload_for('instagram',c.CHANNELS['instagram'],old,'video',{})
        self.assertEqual(p['text'],old['provider_text'])
    def test_youtube_only_owner_attribution_removed(self):
        old={'provider_text':'Steven Bick’s full personal tribute. '+c.PAGE}
        p=c.payload_for('youtube',c.CHANNELS['youtube'],old,'video',{'cardTeaser':'Mart Allen'})
        self.assertEqual(p['text'],'The full personal tribute. '+c.PAGE)
        self.assertEqual(p['metadata']['youtube']['title'],'Mart Allen')

if __name__=='__main__':unittest.main()
