import unittest
from pathlib import Path
from unittest.mock import patch
import requests
from streamlit.testing.v1 import AppTest
from rotation import CROPS,BY_NAME,assess,shortlist
ROOT=Path(__file__).parent

def app(page='farm',language='en'):
    source=(ROOT/'app.py').read_text().replace('ROOT=Path(__file__).parent',f'ROOT=Path({str(ROOT.resolve())!r})').replace('page.run()',page+'()')
    at=AppTest.from_string(source)
    at.session_state['lang']=language
    return at.run(timeout=20)

class Tests(unittest.TestCase):
    def test_catalogue(self):
        self.assertEqual(len(CROPS),250)
        for key in ['id','en','ar']:
            self.assertEqual(len({c[key] for c in CROPS}),250)
        self.assertTrue(all(c['local_suitability']=='not_validated' for c in CROPS))
    def test_screens(self):
        cid=lambda x:BY_NAME[x]['id']
        self.assertEqual(assess(cid('Wheat'),cid('Wheat')),'repeat')
        self.assertEqual(assess(cid('Tomato'),cid('Potato')),'same_family')
        self.assertEqual(assess(cid('Wheat'),cid('Faba bean')),'different_family')
        self.assertEqual(assess(cid('Mango'),cid('Wheat')),'perennial')
        self.assertEqual(shortlist(cid('Mango'),'soil'),[])
        for c in CROPS:
            for p in ['water','soil','balanced']:
                for result in shortlist(c['id'],p):
                    self.assertEqual(assess(c['id'],result['id']),'different_family')
    def test_all_pages_both_languages(self):
        for lang in ['en','ar']:
            for page in ['farm','weather','compare','report']:
                at=app(page,lang)
                self.assertFalse(at.exception,(lang,page,at.exception))
    def test_language_retains_profile(self):
        at=app()
        at.selectbox[2].select(BY_NAME['Tomato']['id'])
        at.button[0].click().run()
        self.assertEqual(at.session_state['profile']['current'],BY_NAME['Tomato']['id'])
        at.radio[0].set_value('ar').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['profile']['current'],BY_NAME['Tomato']['id'])
        self.assertEqual(at.selectbox[2].value,BY_NAME['Tomato']['id'])
    def test_candidate_button(self):
        at=app('compare')
        chosen=shortlist(at.session_state['profile']['current'],'water')[0]['id']
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['profile']['desired'],chosen)
        self.assertEqual(at.selectbox[1].value,chosen)
    def test_api_failure_visible_in_arabic(self):
        at=app('weather','ar')
        with patch('requests.get',side_effect=requests.Timeout):at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertTrue(at.error)
        self.assertIn('البيانات',at.error[0].value)

if __name__=='__main__':unittest.main()
