import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import striking_visual as visual
import striking_queue as publisher
from PIL import Image

class StrikingVisualTests(unittest.TestCase):
    def test_full_observation_and_url_handling(self):
        self.assertEqual(visual.observation('A useful fact. https://example.com/'), 'A useful fact.')
        with self.assertRaises(ValueError): visual.observation('https://example.com/')

    def test_dedicated_image_no_morning_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            issue = {'date':'2026-11-13','strikingText':'A useful qualified forestry observation. https://woodsrun.forestenterprise.org/2026/11/13/'}
            path = visual.render(issue, root)
            self.assertEqual(path.relative_to(root).as_posix(),'assets/striking/2026-11-13.png')
            with Image.open(path) as image:
                self.assertEqual(image.size,(1200,675))
            desc = visual.describe(issue, root)
            self.assertEqual(desc['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertNotIn('/assets/cards/',desc['url'])

    def test_never_truncates_long_unbreakable_word(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'fit in full'):
                visual.render({'date':'2026-11-13','strikingText':'a'*280},Path(folder))

    def test_provider_exact_media_and_morning_card_rejected(self):
        desc = {'url':'https://example.com/assets/striking/d.png'}
        visual.validate_provider_asset({'assets':[{'source':desc['url']}]},desc)
        for assets in [[],[{'source':'https://example.com/assets/cards/d.png'}],
                       [{'source':desc['url']},{'source':'https://example.com/assets/cards/d.png'}]]:
            with self.assertRaises(ValueError): visual.validate_provider_asset({'assets':assets},desc)

    def test_native_image_keeps_caption_and_existing_schedule(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); issue={'date':'2026-11-13','url':'/2026/11/13/','strikingText':'A useful fact. https://woodsrun.forestenterprise.org/2026/11/13/'}
            visual.render(issue, root); desc=visual.describe(issue,root)
            due=datetime(2026,11,13,17,tzinfo=timezone.utc)
            post={'id':'accepted','status':'scheduled','dueAt':publisher.buffer.iso(due),'assets':[{'source':desc['url']}]}
            with patch.object(publisher,'ROOT',root),patch.object(publisher,'load_request',return_value=({'date':issue['date']},issue,issue['strikingText'],due)),patch.object(publisher,'history',return_value=([],None)),patch.object(publisher,'persist') as persist,patch.object(publisher.buffer,'now',return_value=due-timedelta(hours=2)),patch.object(publisher.adapter,'fetch_public',side_effect=[(200,b'page','text/html'),(200,visual.asset_path(root,issue['date']).read_bytes(),'image/png')]),patch.object(publisher.buffer,'gql',return_value={'createPost':{'post':post}}) as gql:
                publisher.schedule()
                payload=gql.call_args.args[1]['input']
                self.assertEqual(payload['text'],issue['strikingText'])
                self.assertEqual(payload['dueAt'],'2026-11-13T17:00:00Z')
                self.assertEqual(payload['assets'],[{'image':{'url':desc['url']}}])
                self.assertEqual(persist.call_args.args[1]['post_id'],'accepted')

    def test_missing_public_visual_prevents_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); issue={'date':'2026-11-13','url':'/2026/11/13/','strikingText':'Fact.'}
            visual.render(issue,root);due=datetime(2026,11,13,17,tzinfo=timezone.utc)
            with patch.object(publisher,'ROOT',root),patch.object(publisher,'load_request',return_value=({'date':issue['date']},issue,'Fact.',due)),patch.object(publisher,'history',return_value=([],None)),patch.object(publisher,'persist') as persist,patch.object(publisher.buffer,'now',return_value=due-timedelta(hours=2)),patch.object(publisher.adapter,'fetch_public',side_effect=[(200,b'page','text/html'),(404,b'','')]),patch.object(publisher.buffer,'gql') as gql:
                with self.assertRaisesRegex(ValueError,'not public'): publisher.schedule()
                gql.assert_not_called();persist.assert_not_called()

if __name__=='__main__': unittest.main()
