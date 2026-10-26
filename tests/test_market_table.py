import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from market_table import render_market_section, table_cells, validate_market_table, ROWS
from prepare_email_payload import compile_payload
from daily_resources import resource_html


class MarketTableTests(unittest.TestCase):
    def fixture(self, section, day='2026-10-27'):
        resource = dict(date=day,source='daily-sheet',cached=False,item=None,unavailable_reason='No eligible resource')
        issue = dict(date=day,displayDate='October '+str(int(day[-2:]))+', 2026',url='/'+day.replace('-','/')+'/',featuredResource=resource)
        page = '<article class="edition-wrap"><h1>'+issue['displayDate']+'</h1>'
        page += '<article class="story"><h3>Lead</h3><p>Lead facts.</p><p>Lead context.</p></article>'
        page += section+'<article class="story"><h3>Second</h3><p>More facts.</p></article>'+resource_html(resource)+'</article>'
        return page, issue

    def test_approved_email_cells_styles_and_links_survive(self):
        table = (Path(__file__).parent/'fixtures/approved_market_table.html').read_text()
        table = table.replace('US$6.276/gal','<a href="https://example.org/observation?a=1&amp;b=2">US$6.276/gal</a>')
        page, issue = self.fixture('<section><h2>By the Numbers</h2>'+table+'<p>Caveat: annualized estimates.</p></section>')
        payload = compile_payload(page, issue)
        source = BeautifulSoup(table,'html.parser').find('table')
        output = BeautifulSoup(payload['html'],'html.parser').select_one('#market-table')
        for old, new in zip(sum(table_cells(source),[]),sum(table_cells(output),[])):
            text = old.get_text(' ',strip=True)
            self.assertEqual(text,new.get_text(' ',strip=True))
            self.assertIn(text,payload['text'])
        self.assertIn('https://example.org/observation?a=1&b=2',payload['all_urls'])
        self.assertIn('https://example.org/observation?a=1&b=2',payload['text'])
        self.assertIn('Caveat: annualized estimates.',payload['text'])
        self.assertEqual([c['style'] for c in output.select('col')],['width:35%','width:33%','width:32%'])
        self.assertEqual([r.find('th')['bgcolor'] for r in output.select('tbody tr')],['#f2f5ee','#fffdf8']*3)
        self.assertEqual(output.select_one('thead th')['bgcolor'],'#243f2c')
        self.assertLess(payload['html'].index('Lead facts'),payload['html'].index('id="market-table"'))
        self.assertLess(payload['html'].index('id="market-table"'),payload['html'].index('More facts'))

    def test_missing_optional_data_does_not_block_and_has_sources(self):
        page, issue = self.fixture(render_market_section('2026-10-27',{}))
        payload = compile_payload(page,issue)
        self.assertEqual(len(BeautifulSoup(payload['html'],'html.parser').select('#market-table tbody tr')),6)
        self.assertIn('Not verified as of 2026-10-27',payload['text'])
        self.assertIn('https://fred.stlouisfed.org/series/WPU0812',payload['all_urls'])

    def test_monthly_dates_contract_and_last_verified_are_inputs(self):
        observations={k:dict(status='last_verified',latest='12',observed='September 2026',change=['−1 point'],comparison='vs. August 2026') for k,_,_ in ROWS}
        observations['lumber_futures']['detail']='January 2027 contract; US$/MBF'
        text=render_market_section('2026-10-28',observations)
        self.assertIn('January 2027 contract',text)
        self.assertNotIn('November 2026',text)
        self.assertIn('September 2026 — last verified; update unavailable',text)
        self.assertNotIn('518.50',text)

    def test_structure_cutover_and_unsafe_content(self):
        page,issue=self.fixture(render_market_section('2026-10-27',{}))
        with self.assertRaises(ValueError): compile_payload(page.replace('Indicator</th>','Wrong</th>'),issue)
        with self.assertRaises(ValueError): compile_payload(page.replace('Unavailable','<script>alert(1)</script>',1),issue)
        with self.assertRaises(ValueError): validate_market_table(BeautifulSoup('<article/>','html.parser'),'2026-10-27')
        validate_market_table(BeautifulSoup('<article/>','html.parser'),'2026-10-26')

    def test_narrow_layout_constraints(self):
        table=BeautifulSoup(render_market_section('2026-10-27',{}),'html.parser').find('table')
        self.assertIn('table-layout:fixed',table['style'])
        self.assertEqual(table['width'],'100%')
        for cell in table.select('tbody th,tbody td'):
            self.assertIn('overflow-wrap:break-word',cell['style'])
            self.assertNotIn('white-space:nowrap',cell['style'])
        # At 320/375px viewports, the fixed fractions fit the available width;
        # no fixed pixel/min-width is introduced on table or columns.
        for viewport in (320,375,600):
            self.assertAlmostEqual(sum(viewport*w/100 for w in (35,33,32)),viewport)


if __name__=='__main__': unittest.main()
