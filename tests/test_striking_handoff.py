import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_striking_request as handoff
import striking_queue as publisher


class HandoffTests(unittest.TestCase):
    def fixture(self, root, date):
        issue = {'date': date, 'url': '/' + date.replace('-', '/') + '/',
                 'strikingText': 'Prepared distinct observation.'}
        (root / 'data/preparation').mkdir(parents=True)
        page = root / date.replace('-', '/') / 'index.html'
        page.parent.mkdir(parents=True)
        page.write_bytes(b'Current edition')
        (root / 'data/issues.json').write_text(json.dumps([issue]))
        sha = hashlib.sha256(json.dumps(issue, sort_keys=True, ensure_ascii=False).encode() + b'\n' + page.read_bytes()).hexdigest()
        receipt = root / 'data/preparation' / (date + '.json')
        receipt.write_text(json.dumps({'date': date, 'ready': True, 'source_sha256': sha}))
        return issue, receipt

    def test_daylight_and_standard_due_times(self):
        for date, hour, due in [('2026-10-20', 15, 16), ('2026-11-02', 16, 17)]:
            with self.subTest(date=date), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root, date)
                now = datetime.fromisoformat(date).replace(hour=hour, minute=40, tzinfo=timezone.utc)
                self.assertTrue(handoff.prepare(root, now))
                request = json.loads((root / 'data/striking-trigger.json').read_text())
                self.assertEqual(request['due_at'], date + 'T' + str(due) + ':00:00Z')
                self.assertEqual(request['date'], date)

    def test_other_cron_slot_never_writes(self):
        for stamp in ['2026-10-20T16:40:00+00:00', '2026-11-02T15:40:00+00:00']:
            with tempfile.TemporaryDirectory() as directory:
                self.assertFalse(handoff.prepare(Path(directory), datetime.fromisoformat(stamp)))
                self.assertFalse(list(Path(directory).iterdir()))

    def test_changed_unprepared_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            issue, receipt = self.fixture(root, '2026-10-20')
            issue['strikingText'] = 'Changed after preparation'
            (root / 'data/issues.json').write_text(json.dumps([issue]))
            with self.assertRaisesRegex(ValueError, 'not completed preparation'):
                handoff.prepare(root, datetime.fromisoformat('2026-10-20T15:40:00+00:00'))
            self.assertFalse((root / 'data/striking-trigger.json').exists())

    def test_stale_issue_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root, '2026-10-19')
            with self.assertRaisesRegex(ValueError, 'missing or invalid'):
                handoff.prepare(root, datetime.fromisoformat('2026-10-20T15:40:00+00:00'))

    def test_existing_post_does_not_mutate_provider(self):
        self.check_publisher(found={'id': 'existing', 'status': 'sent'})

    def test_ambiguous_receipt_does_not_resubmit(self):
        self.check_publisher(record=True, error='unresolved')

    def test_late_submission_does_not_publish(self):
        self.check_publisher(error='deadline missed')

    def check_publisher(self, found=None, record=False, error=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            due = datetime(2026, 10, 19, 16, tzinfo=timezone.utc)
            text = 'Prepared distinct observation.'
            if record:
                path.write_text(json.dumps({'text': text, 'due_at': publisher.buffer.iso(due)}))
            with patch.object(publisher, 'load_request', return_value=({'date': '2026-10-19'}, {}, text, due)), patch.object(publisher, 'receipt_path', return_value=path), patch.object(publisher, 'history', return_value=([], found)), patch.object(publisher, 'persist'), patch.object(publisher.buffer, 'now', return_value=due), patch.object(publisher.buffer, 'gql') as mutation:
                if error:
                    with self.assertRaisesRegex(ValueError, error):
                        publisher.schedule()
                else:
                    publisher.schedule()
                mutation.assert_not_called()


if __name__ == '__main__':
    unittest.main()
