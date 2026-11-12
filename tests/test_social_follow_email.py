"""Offline regressions for the email-only social footer; no provider calls."""
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_email_payload import compile_payload, SOCIAL_FOLLOW_LINKS, UNSUB
from test_brandx_sponsor import fixture


def navigation():
    return '<nav class="social-follow">'+''.join(
        f'<a href="{url}">{name}</a>' for name, url in SOCIAL_FOLLOW_LINKS)+'</nav>'


class SocialFollowEmailTests(unittest.TestCase):
    def payload(self, day='2026-11-11', nav='', inside=False):
        page, issue = fixture(day, panel=day in ('2026-11-09', '2026-11-16'))
        page = page.replace('</article>', nav+'</article>', 1) if inside else page+nav
        return compile_payload(page, issue)

    def test_cutover_and_future_monday(self):
        for day in ('2026-11-09', '2026-11-10'):
            self.assertNotIn('Follow along', self.payload(day)['html'])
        for day in ('2026-11-11', '2026-11-12', '2026-11-16'):
            with self.subTest(day=day):
                self.assertIn('Follow along', self.payload(day)['html'])

    def test_four_buttons_plain_links_and_owner_variant(self):
        p = self.payload()
        for variant in ('html', 'owner_test_html'):
            soup = BeautifulSoup(p[variant], 'html.parser')
            table = soup.select_one('table.social-follow')
            self.assertEqual(table['role'], 'presentation')
            self.assertEqual(table['width'], '100%')
            self.assertEqual(len(table.find_all('tr')), 2)
            self.assertTrue(all(len(row.find_all('td')) == 2 for row in table.find_all('tr')))
            self.assertEqual([(a.text, a['href']) for a in table.find_all('a')], list(SOCIAL_FOLLOW_LINKS))
            self.assertLess(p[variant].index('Read today’s web edition'), p[variant].index('Follow along'))
            for name, url in SOCIAL_FOLLOW_LINKS:
                a = table.find('a', href=url)
                self.assertEqual(a['aria-label'], 'Follow on '+name)
                self.assertIn('padding:12px', a['style'])
                self.assertEqual(p[variant].count('href="'+url+'"'), 1)
        for variant in ('text', 'owner_test_text'):
            for name, url in SOCIAL_FOLLOW_LINKS:
                self.assertIn(name+': '+url, p[variant])
        self.assertLess(p['html'].index('Follow along'), p['html'].index(UNSUB))
        self.assertNotIn(UNSUB, p['owner_test_html'])
        self.assertNotIn(UNSUB, p['owner_test_text'])
        self.assertTrue(set(url for _, url in SOCIAL_FOLLOW_LINKS) <= set(p['all_urls']))
        self.assertFalse(set(url for _, url in SOCIAL_FOLLOW_LINKS) & set(p['source_urls']))

    def test_nav_inside_or_outside_article_consumed_once(self):
        baseline = self.payload()
        for inside in (False, True):
            p = self.payload(nav=navigation(), inside=inside)
            self.assertEqual(p, baseline)

    def test_icon_only_label_is_accepted(self):
        nav = navigation().replace('>X</a>', '><img alt="X" src="/assets/social/x.png"></a>')
        self.assertEqual(self.payload(nav=nav), self.payload())

    def test_nested_artwork_attribution_link_is_not_a_profile(self):
        nav = navigation().replace(
            '</nav>',
            '<small>Artwork by <a href="https://icons8.com/">Icons8</a></small></nav>')
        self.assertEqual(self.payload(nav=nav), self.payload())

    def test_bad_names_urls_missing_extra_or_duplicate_rejected(self):
        nav = navigation()
        for bad in (nav+nav, nav.replace('>X<', '>Twitter<'),
                    nav.replace('https://x.com/ForestBizSchool', 'https://x.com/wrong'),
                    nav.replace('</nav>', '<a href="https://example.org/">Other</a></nav>'),
                    nav.replace('<a href="https://x.com/ForestBizSchool">X</a>', ''),
                    nav.replace('<nav ', '<div ').replace('</nav>', '</div>')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.payload(nav=bad)


if __name__ == '__main__':
    unittest.main()
