import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from delivery_policy import resolve
from delivery_after_prepare import validate_source

P = {'timezone':'America/Denver','daily':{'enabled':True,'queue_after':'02:30:00','time':'04:00:00'},'tests':[{'enabled':True,'date':'2026-10-08','test_run_id':'E2E-20261008-1600','queue_after':'2026-10-08T15:30:00-06:00','due_at':'2026-10-08T16:00:00-06:00'}]}

class DeliveryTests(unittest.TestCase):
    def at(self, value): return resolve(P, datetime.fromisoformat(value))
    def test_no_early_test(self): self.assertIsNone(self.at('2026-10-08T15:29:00-06:00'))
    def test_explicit_test(self):
        request=self.at('2026-10-08T15:35:00-06:00')
        self.assertEqual(request['test_run_id'],'E2E-20261008-1600')
        self.assertEqual(request['due_at'],'2026-10-08T22:00:00Z')
        self.assertEqual(request['channels'],['x','instagram','youtube'])
    def test_past_due_no_force(self): self.assertIsNone(self.at('2026-10-08T16:01:00-06:00'))
    def test_minimum_lead(self): self.assertIsNone(self.at('2026-10-08T15:59:30-06:00'))
    def test_next_day_not_old_test(self):
        q=self.at('2026-10-09T03:05:00-06:00')
        self.assertEqual(q['action'],'schedule_daily')
        self.assertEqual(q['date'],'2026-10-09')
        self.assertEqual(q['due_at'],'2026-10-09T10:00:00Z')
        self.assertNotIn('test_run_id',q)
    def test_winter_time(self): self.assertEqual(self.at('2026-11-02T03:30:00-07:00')['due_at'],'2026-11-02T11:00:00Z')
    def test_before_preparation_window(self): self.assertIsNone(self.at('2026-10-09T01:00:00-06:00'))
    def test_no_naive_time(self):
        with self.assertRaises(ValueError): resolve(P,datetime(2026,10,8,15,35))
    def test_ambiguous_tests(self):
        policy=dict(P,tests=P['tests']*2)
        with self.assertRaises(ValueError): resolve(policy,datetime.fromisoformat('2026-10-08T15:35:00-06:00'))
    def test_source_receipt_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'data/preparation').mkdir(parents=True)
            (root/'2026/10/08').mkdir(parents=True)
            (root/'assets').mkdir()
            issue={'date':'2026-10-08','displayDate':'October 8, 2026'}
            page=b'<h1>October 8, 2026</h1>'
            (root/'2026/10/08/index.html').write_bytes(page)
            (root/'data/issues.json').write_text(json.dumps([issue]))
            record={'date':issue['date'],'ready':True,'source_sha256':hashlib.sha256(json.dumps(issue,sort_keys=True,ensure_ascii=False).encode()+b'\n'+page).hexdigest()}
            for kind in ('card','video'):
                (root/'assets'/kind).write_bytes(kind.encode())
                record[kind]={'path':'assets/'+kind,'sha256':hashlib.sha256(kind.encode()).hexdigest()}
            (root/'data/preparation/2026-10-08.json').write_text(json.dumps(record))
            validate_source(root,{'date':'2026-10-08'})
            (root/'assets/video').write_bytes(b'changed')
            with self.assertRaises(ValueError):validate_source(root,{'date':'2026-10-08'})

if __name__=='__main__':unittest.main()
