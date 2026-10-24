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

    def test_explicit_preflight_checks_both_fields_and_preserves_history(self):
        issue = {'date': '2026-10-25', 'cardTeaser': 'Headline', 'cardSubhead': 'Context'}
        with patch.object(cards, 'fit_wrapped_text', return_value=(None, [])) as fit:
            cards.check_card_text_fit(issue)
            self.assertEqual(len(fit.call_args_list), 2)
            self.assertTrue(all(call.kwargs['allow_truncation'] is False for call in fit.call_args_list))
            fit.reset_mock()
            cards.check_card_text_fit(dict(issue, date='2026-10-24'))
            fit.assert_not_called()

    def test_generation_does_not_invoke_strict_preflight(self):
        with patch.object(cards, 'font'), patch.object(cards.ImageDraw, 'Draw'), \
             patch.object(cards, 'check_card_text_fit') as check, \
             patch.object(cards, 'fit_wrapped_text', return_value=(None, [])) as fit:
            cards.render_teaser_card(None, {'cardTeaser': 'Headline', 'cardSubhead': 'Context'},
                                     date(2026, 10, 25), 'Sunday')
            check.assert_not_called()
            self.assertEqual(len(fit.call_args_list), 2)
            self.assertTrue(all('allow_truncation' not in call.kwargs for call in fit.call_args_list))


if __name__ == '__main__':
    unittest.main()
