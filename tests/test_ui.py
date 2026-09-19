import json
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=sync_playwright().start(); cls.addClassCleanup(cls.p.stop)
        chrome='C:/Program Files/Google/Chrome/Application/chrome.exe'
        cls.browser=cls.p.chromium.launch(executable_path=chrome if Path(chrome).exists() else None)
        cls.addClassCleanup(cls.browser.close)
    def setUp(self):
        self.page=self.browser.new_page(); self.addCleanup(self.page.close)
        self.state=json.loads((ROOT/'tests/fixtures/ui/state_initial.json').read_text(encoding='utf-8-sig'))
        def serve(route):
            path=urlparse(route.request.url).path
            if path=='/api/state': route.fulfill(json=self.state)
            elif path=='/api/prepare':
                self.state.update(busy=True,stage='Daytona 환경 준비 중')
                route.fulfill(status=202,json={'accepted':True})
            elif path.startswith('/static/'):
                file=ROOT/path.lstrip('/')
                route.fulfill(path=str(file))
            elif path=='/': route.fulfill(path=str(ROOT/'static/index.html'),content_type='text/html')
            else: route.fulfill(status=404)
        self.page.route('http://ui.test/**',serve)
    def test_prepare_button_stays_disabled_during_busy_job(self):
        self.page.goto('http://ui.test/')
        self.page.locator('#btn-prepare').click()
        self.page.wait_for_function("document.querySelector('#status-busy').textContent==='실행 중'")
        self.assertFalse(self.page.locator('#btn-prepare').is_enabled())
    def test_image_evidence_and_model_details_are_visible(self):
        self.state=json.loads((ROOT/'tests/fixtures/ui/state_fixed_pass.json').read_text(encoding='utf-8-sig'))
        self.state['runs'][0]['alt_text']={'status':'complete','error':None,'items':[
            {'target':'#offer','image_url':'/artifacts/example/image-0.png','supplied_text':'할인 안내',
             'status':'complete','verdict':'pass','summary':'일치','provider':'openai','model':'gpt-4.1-mini',
             'elapsed_ms':2000,'checks':[{'visual_evidence':'50% OFF','provided_evidence':'50% 할인','reason':'동일한 할인율'}]}]}
        self.page.goto('http://ui.test/')
        self.page.wait_for_function("document.querySelector('#alt-items').textContent.includes('일치')")
        self.assertEqual(self.page.locator('#alt-items img').count(),1)
        self.assertIn('gpt-4.1-mini',self.page.locator('#alt-items').inner_text())
        self.assertIn('50% OFF',self.page.locator('#alt-items').inner_text())

    def test_audio_quotes_and_section_timings_are_visible(self):
        self.state=json.loads((ROOT/'tests/fixtures/ui/state_fixed_pass.json').read_text(encoding='utf-8-sig'))
        self.state['runs'][0]['alt_text'].update(status='complete',elapsed_ms=3210)
        self.page.goto('http://ui.test/')
        self.page.wait_for_function("document.querySelector('#audio-checks').textContent.includes('delivered')")
        checks=self.page.locator('#audio-checks').inner_text()
        self.assertIn('결제에 실패했습니다.',checks)
        self.assertIn('결제가 완료되지 않았습니다.',checks)
        self.assertIn('48ms',self.page.locator('#rules-status').inner_text())
        self.assertIn('3210ms',self.page.locator('#alt-status').inner_text())

if __name__=='__main__': unittest.main()
