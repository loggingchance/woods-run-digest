import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_social_cards as cards


class CardHeadlineFitTests(unittest.TestCase):
    def setUp(self):
        self.draw = ImageDraw.Draw(Image.new('RGB', (1200, 630)))

    def test_full_organization_names_fit_intact(self):
        for text in (
            'Packaging Corporation of America mills run flat out, but higher costs loom',
            'Oak Ridge National Laboratory examines new uses for wood',
            'National Forest Products Week puts new uses for wood in the spotlight',
        ):
            with self.subTest(text=text):
                _, rows = cards.fit_wrapped_text(self.draw, text, cards.FONT_SERIF_BOLD,
                                                1010, 3, 52, 39, allow_truncation=False)
                self.assertEqual(' '.join(rows), text)

    def test_overflow_requires_editorial_revision(self):
        for text in ('Qualified reporting ' * 100, 'W' * 100):
            with self.subTest(text=text[:30]), self.assertRaisesRegex(ValueError, 'fit in full'):
                cards.fit_wrapped_text(self.draw, text, cards.FONT_SERIF_BOLD,
                                       1010, 3, 52, 39, allow_truncation=False)

    def test_historical_overflow_keeps_legacy_behavior(self):
        _, rows = cards.fit_wrapped_text(self.draw, 'Qualified reporting ' * 100,
                                        cards.FONT_SERIF_BOLD, 1010, 3, 52, 39)
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[-1].endswith('…'))

    def test_cutover_applies_to_teaser_and_subhead(self):
        # Test routing independently of artwork, drawing and typography.
        for day, expected in ((24, True), (25, False)):
            with patch.object(cards, 'font'), patch.object(cards.ImageDraw, 'Draw'), \
                 patch.object(cards, 'fit_wrapped_text', return_value=(None, [])) as fit:
                cards.render_teaser_card(None, {'cardTeaser': 'Headline', 'cardSubhead': 'Context'},
                                         date(2026, 10, day), 'Sunday')
                self.assertEqual(len(fit.call_args_list), 2)
                self.assertTrue(all(call.kwargs['allow_truncation'] == expected for call in fit.call_args_list))


if __name__ == '__main__':
    unittest.main()
