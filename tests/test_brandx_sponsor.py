import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from brandx_sponsor import validate_sponsor
from market_table import render_market_section
from prepare_email_payload import compile_payload
from sync_public_editorial import validate

TEMPLATE = (Path(__file__).resolve().parents[1]/'scripts/brandx_panel.html').read_text()

def fixture(day='2026-11-09', panel=True):
    d=date.fromisoformat(day)
    display=d.strftime('%B')+f' {d.day}, {d.year}'
    issue=dict(date=day,displayDate=display,url='/'+day.replace('-','/')+'/',summary='Fixture',socialText='Fixture',cardTeaser='Fixture',cardSubhead='Fixture',strikingText='Fixture',featuredResource={'date':day,'source':'daily-sheet','item':None,'unavailable_reason':'Test fixture'})
    page='<article class="edition-wrap"><h1>'+display+'</h1>'
    page+=''.join('<article class="story"><h3>Fixture '+str(n)+'</h3><p>Source paragraph '+str(n)+' <a href="https://example.org/story/'+str(n)+'">Source</a></p><p>Additional fixture text.</p></article>' for n in range(5))
    if d.weekday()<5:page+=render_market_section(day,{})
    page+='<h2>Action Detector</h2><p>Fixture action.</p><h2>Under the Radar</h2><p>Fixture news.</p><section class="wet-woods-box"><h2>Today\'s Featured Resource</h2><p>No featured resource is available for this edition.</p></section>'
    if panel:page+='<section class="brandx-sponsor" data-sponsor="brandx" data-sponsor-date="'+day+'">'+TEMPLATE+'</section>'
    page+='<section class="growth-strip"><h2>Useful enough to pass along?</h2><p>Share the digest.</p><div class="growth-actions"><a href="https://woodsrun.forestenterprise.org/subscribe/">Subscribe</a></div></section></article>'
    return page,issue

class SponsorTests(unittest.TestCase):
    def test_full_compile_and_sync(self):
        page,issue=fixture();validate(page,issue)
        payload=compile_payload(page,issue)
        soup=BeautifulSoup(payload['html'],'html.parser')
        panel=soup.select_one('.brandx-sponsor')
        self.assertIsNotNone(panel)
        self.assertEqual(panel.find_next_sibling().get_text(),'Useful enough to pass along?')
        self.assertEqual(len(soup.select('#brandx-revised-panel')),1)
        self.assertEqual(len(soup.select('table#market-table')),1)
        self.assertEqual(len(panel.select('img')),2)
        self.assertEqual(len(panel.select('table')),3)
        for value in ['Today’s edition is sponsored by','From log to lumber in the swing of a blade','https://www.brandxsawmills.com/','Brand X’s swing-frame mill']:
            self.assertIn(value,payload['text'])
        self.assertIn('background:#991c20;',payload['html'])
        self.assertIn('{{{RESEND_UNSUBSCRIBE_URL}}}',payload['html'])
        self.assertTrue(payload['links_preserved'])
    def test_mondays_ongoing_including_dst(self):
        for day in ['2026-11-09','2026-11-16','2027-03-08','2027-11-08','2030-01-07']:
            page,issue=fixture(day);self.assertIsNotNone(validate_sponsor(BeautifulSoup(page,'html.parser'),day))
    def test_non_mondays_and_historical(self):
        for n in range(7):
            day=(date(2026,11,8)+timedelta(days=n)).isoformat()
            if day=='2026-11-09':continue
            page,issue=fixture(day,False);self.assertIsNone(validate_sponsor(BeautifulSoup(page,'html.parser'),day))
            page,issue=fixture(day)
            with self.assertRaises(ValueError):compile_payload(page,issue)
        page,issue=fixture('2026-11-02')
        with self.assertRaises(ValueError):validate_sponsor(BeautifulSoup(page,'html.parser'),issue['date'])
    def test_missing_panel_rejected(self):
        page,issue=fixture(panel=False)
        with self.assertRaises(ValueError):compile_payload(page,issue)
    def test_altered_payload_rejected(self):
        page,issue=fixture()
        for old,new in [('brandx-photo.png','evil.png'),('https://www.brandxsawmills.com/','https://evil.example/'),('Built in the USA','Different copy'),('background:#991c20;','background:blue;'),('<h2 style=','<script>alert(1)</script><h2 style='),('width="558"','onload="alert(1)" width="558"'),('data-sponsor-date="2026-11-09"','data-sponsor-date="2026-11-16"')]:
            with self.subTest(old=old),self.assertRaises(ValueError):compile_payload(page.replace(old,new),issue)
    def test_wrong_position_and_duplicate_rejected(self):
        page,issue=fixture()
        with self.assertRaises(ValueError):compile_payload(page.replace('<section class="growth-strip">','<p>Intervening text</p><section class="growth-strip">'),issue)
        soup=BeautifulSoup(page,'html.parser');soup.article.append(BeautifulSoup(str(soup.select_one('.brandx-sponsor')),'html.parser'))
        with self.assertRaises(ValueError):compile_payload(str(soup),issue)
    def test_whitespace_does_not_change_approval(self):
        page,issue=fixture();validate_sponsor(BeautifulSoup(page.replace('\n','\n  '),'html.parser'),issue['date'])

if __name__=='__main__':unittest.main()
