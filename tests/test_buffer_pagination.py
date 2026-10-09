import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import buffer_queue


def page(ids, more=False, cursor=None):
    return {'posts': {'edges': [{'node': {'id': x}} for x in ids],
                      'pageInfo': {'hasNextPage': more, 'endCursor': cursor}}}


class BufferHistoryTests(unittest.TestCase):
    def test_full_final_page_is_complete(self):
        with patch.object(buffer_queue, 'gql', return_value=page(list(map(str, range(100))))):
            self.assertEqual(len(buffer_queue.recent('org', 'channel')), 100)

    def test_duplicate_can_be_found_beyond_first_page(self):
        with patch.object(buffer_queue, 'gql', side_effect=[page(['new'], True, 'next'), page(['older-delivery'])]) as api:
            self.assertEqual([p['id'] for p in buffer_queue.recent('org', 'channel')], ['new', 'older-delivery'])
            self.assertEqual(api.call_args_list[1].args[1]['after'], 'next')

    def test_missing_pagination_cannot_authorize_creation(self):
        with patch.object(buffer_queue, 'gql', return_value={'posts': {'edges': []}}):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                buffer_queue.recent('org', 'channel')

    def test_repeated_cursor_cannot_authorize_creation(self):
        with patch.object(buffer_queue, 'gql', return_value=page(['one'], True, 'same')):
            with self.assertRaisesRegex(ValueError, 'did not advance'):
                buffer_queue.recent('org', 'channel')

    def test_page_limit_cannot_authorize_creation(self):
        with patch.object(buffer_queue, 'gql', side_effect=[page([str(i)], True, str(i)) for i in range(100)]):
            with self.assertRaisesRegex(ValueError, 'bounded'):
                buffer_queue.recent('org', 'channel')
