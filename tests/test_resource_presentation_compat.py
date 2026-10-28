import copy
import json
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from daily_resources import validate_feature
from sync_public_editorial import validate
from prepare_email_payload import compile_payload
from video_featured_resource import read_featured_resource

class ResourcePresentationCompatibility(unittest.TestCase):
    def setUp(self):
        self.issue = next(i for i in json.loads((ROOT/'data/issues.json').read_text()) if i['date']=='2026-10-28')
        self.page = (ROOT/'2026/10/28/index.html').read_text()

    def corrected(self):
        soup=BeautifulSoup(self.page,'html.parser')
        box=soup.select_one('section.wet-woods-box')
        title=box.h2
        title.name='h3'
        kicker=box.select_one('.section-kicker')
        kicker.name='h2'; kicker['class']=['resource-heading']
        kicker.string="Today's Featured Resource"
        description=next(p for p in box.find_all('p') if not p.find('a'))
        description.string=self.issue['featuredResource']['item']['description']
        return soup

    def test_historical_and_corrected_shapes_validate(self):
        for page in (self.page,str(self.corrected())):
            self.assertEqual(validate_feature(BeautifulSoup(page,'html.parser'),self.issue),self.issue['featuredResource']['item'])
            validate(page,self.issue)

    def test_full_email_retains_resource_and_table(self):
        page=str(self.corrected()); payload=compile_payload(page,self.issue)
        rendered=BeautifulSoup(payload['html'],'html.parser')
        heading=next(h for h in rendered.find_all('h2') if h.get_text()=="Today's Featured Resource")
        other=next(h for h in rendered.find_all('h2') if h.get_text()=='Action Detector')
        self.assertEqual(heading['style'],other['style'])
        item=self.issue['featuredResource']['item']
        self.assertIn(item['description'],payload['text'])
        self.assertIn(item['url'],payload['all_urls'])
        self.assertEqual(len(rendered.select('#market-table td, #market-table th')),21)
        self.assertNotIn('app: CARBINE',payload['html'])

    def test_metadata_kind_need_not_be_visible(self):
        issue=copy.deepcopy(self.issue); issue['featuredResource']['item']['kind']='interactive-tool'
        validate_feature(self.corrected(),issue)
        del issue['featuredResource']['item']['kind']
        with self.assertRaisesRegex(ValueError,'missing kind'):validate_feature(self.corrected(),issue)

    def test_rejects_wrong_title_description_link_and_duplicate(self):
        for field in ('title','description'):
            issue=copy.deepcopy(self.issue);issue['featuredResource']['item'][field]='NOT THE PUBLISHED VALUE'
            with self.assertRaisesRegex(ValueError,'metadata/page mismatch'):validate_feature(self.corrected(),issue)
        soup=self.corrected();soup.select_one('.book-button')['href']='https://wrong.example/'
        with self.assertRaisesRegex(ValueError,'link mismatch'):validate_feature(soup,self.issue)
        soup=self.corrected();soup.article.append(copy.copy(soup.select_one('.wet-woods-box')))
        with self.assertRaisesRegex(ValueError,'exactly one'):validate_feature(soup,self.issue)

    def test_explicit_unavailable_corrected_shape(self):
        issue=copy.deepcopy(self.issue)
        issue['featuredResource'].update(item=None,unavailable_reason='No eligible resource')
        soup=self.corrected();box=soup.select_one('.wet-woods-box')
        box.clear();box.append(BeautifulSoup('<h2 class="resource-heading">Today\'s Featured Resource</h2><p>No featured resource is available for this edition.</p>','html.parser'))
        self.assertIsNone(validate_feature(soup,issue))

    def test_video_uses_same_canonical_metadata(self):
        resource=read_featured_resource(ROOT,self.issue['date'],self.issue)
        self.assertEqual(resource['url'],self.issue['featuredResource']['item']['url'])
        self.assertEqual(resource['title'],self.issue['featuredResource']['item']['title'])

if __name__=='__main__': unittest.main()
