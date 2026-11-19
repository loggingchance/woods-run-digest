import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_queue as q

ISSUE = {'date': '2026-11-19', 'displayDate': 'November 19, 2026', 'url': '/2026/11/19/'}
CHANNEL = q.TARGETS['instagram'][2]
RAW = 'https://raw.githubusercontent.com/loggingchance/woods-run-digest/main'
def post(pid='daily', source=None, mime='video/mp4'):
    return {'id': pid, 'channelId': CHANNEL, 'text': 'Woods Run Digest — November 19, 2026',
            'assets': [{'source': source or RAW + '/assets/videos/2026-11-19.mp4', 'mimeType': mime}],
            'status': 'scheduled', 'dueAt': '2026-11-19T20:00:00Z'}
def recruitment():
    return post('stale', RAW + '/assets/instagram-recruitment/2026-11-19-cooperage.jpg', 'image/jpeg')

class IdentityTests(unittest.TestCase):
    def test_canonical_raw_and_public_alias(self):
        for url in [RAW + '/assets/videos/2026-11-19.mp4', q.adapter.SITE_ROOT + '/assets/videos/2026-11-19.mp4']:
            self.assertTrue(q.instagram_daily_identity(post(source=url), ISSUE))
    def test_reject_wrong_sources_type_channel_and_test(self):
        cases = [recruitment(), post(source=RAW+'/assets/cards/2026-11-19.mp4'),
                 post(source='https://evil.example/assets/videos/2026-11-19.mp4'),
                 post(source=RAW+'/assets/videos/2026-11-18.mp4'), post(mime='image/jpeg'),
                 post(source=RAW+'/assets/videos/2026-11-19.mp4?other=1')]
        other = post(); other['channelId'] = 'wrong'; cases.append(other)
        test = post(); test['text'] += ' [WR TEST sample]'; cases.append(test)
        for p in cases:
            with self.subTest(post=p): self.assertFalse(q.matches(p, ISSUE, None, p['id'], 'instagram'))
    def test_caption_and_link_do_not_turn_image_into_reel(self):
        p = recruitment(); p['text'] += ' ' + q.adapter.SITE_ROOT + ISSUE['url']
        self.assertFalse(q.instagram_daily_identity(p, ISSUE))
    def test_stale_id_requires_explicit_recovery(self):
        for posts in [[recruitment()], [recruitment(), post()], []]:
            with self.assertRaisesRegex(ValueError, 'explicit recovery'):
                q.instagram_candidates(posts, ISSUE, {'post_id':'stale'}, {}, ['instagram'], 'schedule_daily', False)
    def test_explicit_recovery_preserves_evidence_and_scans_real_candidates(self):
        r={'post_id':'stale'}
        found=q.instagram_candidates([recruitment(),post()], ISSUE, r,
            {'replace_mismatched_instagram_post_id':'stale'}, ['instagram'], 'schedule_daily', False)
        self.assertEqual([p['id'] for p in found], ['daily'])
        self.assertEqual(r['post_id'],'stale')
        self.assertEqual(r['rejected_identity_evidence'][0]['provider_post'], recruitment())
        q.instagram_candidates([recruitment()], ISSUE, r,
            {'replace_mismatched_instagram_post_id':'stale'}, ['instagram'], 'schedule_daily', False)
        self.assertEqual(len(r['rejected_identity_evidence']),1)
    def test_recovery_refuses_missing_valid_uncertain_wrong_id_and_scope(self):
        for posts,r,selected,action,test in [
            ([],{'post_id':'stale'},['instagram'],'schedule_daily',False),
            ([post('stale')],{'post_id':'stale'},['instagram'],'schedule_daily',False),
            ([recruitment()],{'post_id':'stale','attempt_started_at':'earlier'},['instagram'],'schedule_daily',False),
            ([recruitment()],{'post_id':'other'},['instagram'],'schedule_daily',False),
            ([recruitment()],{'post_id':'stale'},['instagram','x'],'schedule_daily',False),
            ([recruitment()],{'post_id':'stale'},['instagram'],'audit',False),
            ([recruitment()],{'post_id':'stale'},['instagram'],'schedule_test',True)]:
            with self.subTest(r=r,selected=selected,action=action), self.assertRaises(ValueError):
                q.instagram_candidates(posts,ISSUE,r,{'replace_mismatched_instagram_post_id':'stale'},selected,action,test)
    def test_successful_recovery_request_can_be_verified_again(self):
        r={'post_id':'daily','attempt_started_at':'earlier','rejected_identity_evidence':[{'post_id':'stale'}]}
        found=q.instagram_candidates([post(),recruitment()],ISSUE,r,
            {'replace_mismatched_instagram_post_id':'stale'},['instagram'],'schedule_daily',False)
        self.assertEqual(len(found),1)
    def test_valid_saved_id_does_not_hide_duplicate_reel(self):
        found=q.instagram_candidates([post(),post('second')],ISSUE,{'post_id':'daily'},{},['instagram'],'schedule_daily',False)
        self.assertEqual(len(found),2)
    def test_other_channel_and_test_matching_unchanged(self):
        self.assertTrue(q.matches({'text':q.adapter.SITE_ROOT+ISSUE['url']},ISSUE,None,key='x'))
        self.assertTrue(q.matches({'id':'saved'},ISSUE,None,'saved','youtube'))
        self.assertTrue(q.matches({'text':'[WR TEST t]'},ISSUE,'[WR TEST t]',key='instagram'))

    def run_case(self, posts, saved, request=None):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); receipt=root/'data/buffer-delivery/daily-2026-11-19.json'
            receipt.parent.mkdir(parents=True); receipt.write_text(json.dumps({'channels':{'instagram':saved}}))
            req={'action':'schedule_daily','date':ISSUE['date'],'channels':['instagram'],'due_at':'2026-11-19T20:00:00Z'}
            req.update(request or {})
            channel={'id':CHANNEL,'service':'instagram','name':'northeastforests'}
            with patch.object(q,'ROOT',root), patch.object(q,'load_issue',return_value=ISSUE), \
                 patch.object(q,'now',return_value=datetime(2026,11,19,18,tzinfo=timezone.utc)), \
                 patch.object(q,'get_channels',return_value=('org',[channel])), \
                 patch.object(q,'recent',return_value=posts), patch.object(q,'gql') as mutate, redirect_stdout(io.StringIO()):
                code=q.run(req)
                self.assertFalse(mutate.called)
            return code,json.loads(receipt.read_text())['channels']['instagram']
    def test_run_wrong_saved_id_fails_without_mutation_and_clears_flags(self):
        code,r=self.run_case([recruitment()],{'post_id':'stale','provider_sent':True,'existing_delivery':True,'schedule_verified':True})
        self.assertEqual(code,1)
        for flag in ['provider_sent','existing_delivery','schedule_verified']: self.assertFalse(r[flag])
        self.assertIn('identity',r['error'])
    def test_run_duplicate_valid_reels_fails_closed(self):
        code,r=self.run_case([post(),post('second')],{})
        self.assertEqual(code,1); self.assertIn('Multiple matching',r['error'])
    def test_run_uncertain_attempt_is_never_retried(self):
        code,r=self.run_case([],{ 'attempt_started_at':'earlier'})
        self.assertEqual(code,1); self.assertIn('unresolved',r['error'])
    def test_run_valid_saved_reel_idempotent(self):
        code,r=self.run_case([post()],{'post_id':'daily'})
        self.assertEqual(code,0); self.assertTrue(r['existing_delivery'])

    def test_authorized_recovery_creates_exact_reel_once_and_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); receipt=root/'data/buffer-delivery/daily-2026-11-19.json'
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({'channels':{'instagram':{'post_id':'stale'}}}))
            req={'action':'schedule_daily','date':ISSUE['date'],'channels':['instagram'],
                 'due_at':'2026-11-19T20:00:00Z','replace_mismatched_instagram_post_id':'stale'}
            channel={'id':CHANNEL,'service':'instagram','name':'northeastforests'}
            with patch.object(q,'ROOT',root), patch.object(q,'load_issue',return_value=ISSUE), \
                 patch.object(q,'now',return_value=datetime(2026,11,19,18,tzinfo=timezone.utc)), \
                 patch.object(q,'get_channels',return_value=('org',[channel])), \
                 patch.object(q,'recent',side_effect=[[recruitment()],[recruitment(),post()]]), \
                 patch.object(q,'preflight',return_value={'video':{'url':RAW+'/assets/videos/2026-11-19.mp4'}}), \
                 patch.object(q,'gql',return_value={'createPost':{'post':post()}}) as mutate, \
                 patch.object(q.adapter,'compose_instagram_post',return_value='Daily caption'), redirect_stdout(io.StringIO()):
                self.assertEqual(q.run(req),0)
                self.assertEqual(q.run(req),0)
                self.assertEqual(mutate.call_count,1)
                payload=mutate.call_args.args[1]['input']
                self.assertEqual(payload['channelId'],CHANNEL)
                self.assertEqual(payload['assets'][0]['video']['url'],RAW+'/assets/videos/2026-11-19.mp4')
            r=json.loads(receipt.read_text())['channels']['instagram']
            self.assertEqual(r['post_id'],'daily')
            self.assertEqual(r['rejected_identity_evidence'][0]['post_id'],'stale')

if __name__=='__main__': unittest.main()
