import datetime
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from book_rotation import ITEMS, featured_item, resource_heading

class HistoricalResourceTests(unittest.TestCase):
    def test_historical_rotation_preserved(self):
        for offset in range(11):
            day = datetime.date(2026, 10, 14) + datetime.timedelta(days=offset)
            self.assertEqual(featured_item(day), ITEMS[offset % 5])
            self.assertEqual(resource_heading(day), 'BOOKS & APPS')

    def test_future_requires_canonical_sheet_selection(self):
        self.assertEqual(resource_heading('2026-10-25'), "Today's Featured Resources")
        with self.assertRaises(ValueError): featured_item('2026-10-25')

if __name__ == '__main__': unittest.main()
