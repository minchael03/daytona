import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
import rules

class ReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=sync_playwright().start(); cls.addClassCleanup(cls.p.stop)
        chrome='C:/Program Files/Google/Chrome/Application/chrome.exe'
        cls.browser=cls.p.chromium.launch(executable_path=chrome if Path(chrome).exists() else None)
        cls.addClassCleanup(cls.browser.close)
    def scan(self,html):
        page=self.browser.new_page(); self.addCleanup(page.close)
        page.set_content('<body style="background:white">'+html+'</body>')
        return rules.scan(page)['findings']
    def finding(self,rows,kind,target):
        return next(r for r in rows if r['rule_id']==kind and r['target']==target)
    def test_hidden_subtree_and_disabled_contrast_excluded(self):
        rows=self.scan('<div style="display:none"><img id="hidden-img"><button id="hidden-button"></button><input id="hidden-input"><p id="hidden-text">hidden</p></div><button disabled id="disabled" style="color:white;background:white">Disabled</button>')
        self.assertFalse(any(r['target'].startswith('#hidden') for r in rows))
        self.assertFalse(any(r['rule_id']=='contrast' and r['target']=='#disabled' for r in rows))
    def test_ancestor_effects_cannot_pass_as_plain_contrast(self):
        for effect in ['opacity:.1','filter:blur(1px)','transform:scale(.8)']:
            rows=self.scan('<div style="'+effect+'"><p id="text" style="color:black;background:white">Text</p></div>')
            self.assertEqual(self.finding(rows,'contrast','#text')['status'],'needs_review')
    def test_decorative_intent_requires_semantic_review(self):
        rows=self.scan('<img id="decorative" role="presentation" width="40" height="40"><img id="aria-hidden" aria-hidden="true" width="40" height="40">')
        for target in ['#decorative','#aria-hidden']:
            self.assertEqual(self.finding(rows,'image_alt',target)['status'],'needs_review')
    def test_browser_names_and_hidden_text(self):
        rows=self.scan('<input type="submit" id="submit"><button id="hidden-name"><span aria-hidden="true">Invisible to AT</span></button><button id="multi"><img alt=""><img alt="Continue"></button><label for="field"><img alt="Customer name"></label><input id="field"><input type="image" alt="Pay" id="image-submit">')
        for target in ['#submit','#multi','#image-submit']:
            self.assertEqual(self.finding(rows,'button_name',target)['status'],'pass')
        self.assertEqual(self.finding(rows,'button_name','#hidden-name')['status'],'fail')
        self.assertEqual(self.finding(rows,'form_label','#field')['status'],'pass')

if __name__=='__main__': unittest.main()
