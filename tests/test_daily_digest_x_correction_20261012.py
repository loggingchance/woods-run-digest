import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import correct_daily_digest_x_20261012 as c

class CorrectionGuards(unittest.TestCase):
    def request(self, **changes):
        r = {'mode': 'audit', 'old_buffer_id': c.OLD_BUFFER, 'old_x_id': c.OLD_X}
        r.update(changes)
        return r

    def test_public_fetch_matches_existing_adapter_contract(self):
        with patch.object(c.adapter, "fetch_public", return_value=(200, b"photo", "image/png")):
            self.assertEqual(c.fetch_public(c.PHOTO), b"photo")

    def test_audit_needs_no_deletion_confirmation(self):
        c.validate_request(self.request())

    def test_publish_refuses_without_explicit_activation(self):
        with self.assertRaises(ValueError):
            c.validate_request(self.request(mode='publish'))

    def test_publish_refuses_without_deletion_confirmation(self):
        with self.assertRaisesRegex(ValueError, 'Awaiting owner confirmation'):
            c.validate_request(self.request(mode='publish', activation=c.ACTIVATION))

    def test_owner_can_authorize_post_before_deletion(self):
        with patch.object(c, 'DATE', c.datetime.now(c.ZoneInfo('America/Denver')).date().isoformat()):
            c.validate_request(self.request(mode='publish', activation=c.ACTIVATION,
                owner_confirmed_old_x_deleted=False, owner_handles_deletion=True,
                owner_allows_replacement_before_deletion=True, authorization_reference='owner-message'))

    def test_owner_handles_deletion_alone_does_not_authorize_posting(self):
        with self.assertRaises(ValueError):
            c.validate_request(self.request(mode='publish', activation=c.ACTIVATION,
                owner_handles_deletion=True, authorization_reference='owner-message'))

    def test_prior_memorial_is_explicitly_distinct(self):
        p = {'id': '6accd289355aa519678a0307', 'text': c.PAGE}
        self.assertIsNone(c.select_existing([p], 'correct', {}))

    def test_wrong_target_fails(self):
        with self.assertRaises(ValueError):
            c.validate_request(self.request(old_x_id='different'))

    def test_uncertain_attempt_cannot_resubmit(self):
        with self.assertRaisesRegex(ValueError, 'Previous attempt unresolved'):
            c.select_existing([], 'text', {'attempt_started_at': 'earlier'})

    def test_other_same_date_post_blocks(self):
        with self.assertRaises(ValueError):
            c.select_existing([{'id': 'other', 'text': 'wrong ' + c.PAGE}], 'correct', {})

    def test_existing_correct_post_is_reused(self):
        p = {'id': 'new', 'text': 'correct ' + c.PAGE, 'assets': [{'source': c.PHOTO}]}
        self.assertEqual(c.select_existing([p], p['text'], {'attempt_started_at': 'earlier'}), p)

    def test_old_receipt_does_not_block_replacement(self):
        self.assertIsNone(c.select_existing([{'id': c.OLD_BUFFER, 'text': c.PAGE}], 'correct', {}))

if __name__ == '__main__':
    unittest.main()
