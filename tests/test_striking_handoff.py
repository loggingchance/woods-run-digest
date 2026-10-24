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

    def test_early_and_delayed_runs_prepare_same_day(self):
        for stamp in ['2026-10-20T09:00:00+00:00', '2026-10-20T19:40:00+00:00', '2026-11-02T15:40:00+00:00']:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root, stamp[:10])
                self.assertTrue(handoff.prepare(root, datetime.fromisoformat(stamp)))
                self.assertEqual(json.loads((root / 'data/striking-trigger.json').read_text())['date'], stamp[:10])

    def test_approved_recovery_is_date_scoped(self):
        for date, expected in [('2026-10-21', '22:05:00Z'), ('2026-10-22', '16:00:00Z')]:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root, date)
                trigger = root / 'data/striking-trigger.json'
                trigger.write_text(json.dumps({'date': date, 'recovery_approval': 'user-2026-10-21T21:57Z'}))
                handoff.prepare(root, datetime.fromisoformat(date + 'T22:00:00+00:00'))
                self.assertEqual(json.loads(trigger.read_text())['due_at'], date + 'T' + expected)

    def test_existing_attempt_keeps_time_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            issue, _ = self.fixture(root, '2026-10-21')
            trigger = root / 'data/striking-trigger.json'
            request = {'date': '2026-10-21', 'due_at': '2026-10-21T22:05:00Z', 'recovery_approval': 'user-2026-10-21T21:57Z'}
            trigger.write_text(json.dumps(request))
            delivery = root / 'data/striking-delivery/2026-10-21.json'
            delivery.parent.mkdir()
            delivery.write_text(json.dumps({'text': issue['strikingText'], 'due_at': request['due_at'], 'state': 'attempt_started'}))
            handoff.prepare(root, datetime.fromisoformat('2026-10-21T23:00:00+00:00'))
            self.assertEqual(json.loads(trigger.read_text()), request)

    def test_changed_unprepared_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            issue, receipt = self.fixture(root, '2026-10-20')
            issue['strikingText'] = 'Changed after preparation'
            (root / 'data/issues.json').write_text(json.dumps([issue]))
            with self.assertRaisesRegex(ValueError, 'not completed preparation'):
                handoff.prepare(root, datetime.fromisoformat('2026-10-20T15:40:00+00:00'))
            self.assertFalse((root / 'data/striking-trigger.json').exists())

    def test_authored_striking_above_buffer_limit_fails_before_trigger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            issue, _ = self.fixture(root, '2026-10-24')
            issue['strikingText'] = 'Original authored observation ' * 12
            (root / 'data/issues.json').write_text(json.dumps([issue]))
            self.assertGreater(len(issue['strikingText']), 280)
            with self.assertRaisesRegex(ValueError, '280'):
                handoff.prepare(root, datetime.fromisoformat('2026-10-24T15:45:00+00:00'))
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

    def test_mismatched_durable_time_fails_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            issue, _ = self.fixture(root, '2026-10-21')
            trigger = root / 'data/striking-trigger.json'
            original = json.dumps({'date': '2026-10-21', 'due_at': '2026-10-21T16:00:00Z'})
            trigger.write_text(original)
            delivery = root / 'data/striking-delivery/2026-10-21.json'
            delivery.parent.mkdir()
            delivery.write_text(json.dumps({'text': issue['strikingText'], 'due_at': '2026-10-21T22:05:00Z', 'state': 'attempt_started'}))
            with self.assertRaisesRegex(ValueError, 'matching durable handoff'):
                handoff.prepare(root, datetime.fromisoformat('2026-10-21T22:00:00+00:00'))
            self.assertEqual(trigger.read_text(), original)

    def test_load_request_recovery_approval_cannot_authorize_other_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root, '2026-10-22')
            (root / 'data/striking-trigger.json').write_text(json.dumps({
                'action': 'schedule_striking', 'date': '2026-10-22',
                'due_at': '2026-10-22T22:05:00Z',
                'recovery_approval': 'user-2026-10-21T21:57Z'}))
            with patch.object(publisher, 'ROOT', root), patch.object(publisher, 'datetime', wraps=datetime) as clock:
                clock.now.return_value = datetime.fromisoformat('2026-10-22T22:00:00+00:00')
                with self.assertRaisesRegex(ValueError, '10:00 America/Denver'):
                    publisher.load_request()

    def test_early_verification_is_read_only_and_checks_exact_schedule(self):
        for provider_due, error in [('2026-10-21T16:00:00Z', False), ('2026-10-21T17:00:00Z', True)]:
            with self.subTest(provider_due=provider_due), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'receipt.json'
                due = datetime.fromisoformat('2026-10-21T16:00:00+00:00')
                path.write_text(json.dumps({'post_id': 'existing'}))
                found = {'id': 'existing', 'status': 'scheduled', 'dueAt': provider_due}
                with patch.object(publisher, 'load_request', return_value=({'date': '2026-10-21'}, {}, 'Observation', due)), patch.object(publisher, 'receipt_path', return_value=path), patch.object(publisher, 'history', return_value=([found], found)), patch.object(publisher, 'persist') as persist, patch.object(publisher.time, 'time', return_value=due.timestamp()-7200), patch.object(publisher.time, 'sleep') as sleep, patch.object(publisher.buffer, 'gql') as mutation:
                    if error:
                        with self.assertRaisesRegex(ValueError, 'no longer verified'):
                            publisher.verify()
                    else:
                        publisher.verify()
                    sleep.assert_not_called()
                    persist.assert_not_called()
                    mutation.assert_not_called()

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

