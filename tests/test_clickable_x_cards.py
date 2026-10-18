import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import buffer_queue as q
import post_to_buffer as a
I={'date':'2026-10-18','displayDate':'October 18, 2026','url':'/2026/10/18/','summary':'Daily news','socialText':'Daily news'}
class Tests(unittest.TestCase):
 def test_daily_x_link_only(self):
  r=q.make_input('x',{'id':'x'},I,{},'2026-10-19T10:00:00Z',None)
  self.assertEqual(r['assets'],[]);self.assertIn(a.SITE_ROOT+I['url'],r['text']);self.assertLessEqual(len(r['text']),280)
 def test_instagram_unchanged(self):
  r=q.make_input('instagram',{'id':'ig'},I,{'video':{'url':'https://example.com/a.mp4'}},'2026-10-19T10:00:00Z',None)
  self.assertTrue(r['metadata']['instagram']['shouldShareToFeed']);self.assertIn('video',r['assets'][0])
 def test_youtube_unchanged(self):
  r=q.make_input('youtube',{'id':'yt'},I,{'video':{'url':'https://example.com/a.mp4'}},'2026-10-19T10:00:00Z',None)
  self.assertEqual(r['metadata']['youtube']['privacy'],'public');self.assertIn('video',r['assets'][0])
 def test_metadata_success(self):
  page=a.SITE_ROOT+I['url'];img=a.SITE_ROOT+'/assets/cards/'+I['date']+'.png'
  h=f'<meta name="twitter:card" content="summary_large_image"><meta property="og:image" content="{img}"><meta property="og:title" content="Daily">'.encode()
  with patch.object(a,'fetch_public',side_effect=[(200,h,'text/html'),(200,b'\x89PNG\r\n\x1a\n','image/png')]):self.assertTrue(a.verify_x_link_card(page,img)['metadata_verified'])
 def test_wrong_card_rejected(self):
  with patch.object(a,'fetch_public',return_value=(200,b'<meta name="twitter:card" content="summary">','text/html')):
   with self.assertRaises(ValueError):a.verify_x_link_card('https://example.com','https://example.com/img.png')
 def test_legacy_recovery_link_card(self):
  with patch.object(a,'graphql',return_value={'createPost':{'post':{'id':'test','assets':[]}}}) as g:
   a.publish('x','text https://example.com','https://example.com/card.png','twitter',link_card=True)
   self.assertEqual(g.call_args[0][1]['input']['assets'],[])
if __name__=='__main__':unittest.main()
