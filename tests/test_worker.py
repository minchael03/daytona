import tempfile
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from worker import collect_images

class WorkerBrowserTests(unittest.TestCase):
    def test_image_evidence_and_sample_final_state(self):
        with sync_playwright() as p, tempfile.TemporaryDirectory() as d:
            browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
            try:
                page=browser.new_page(viewport={'width':1000,'height':760})
                page.goto((Path(__file__).resolve().parents[1]/'sample'/'index.html').as_uri())
                page.locator('#pay').click()
                page.locator('#payment-status[data-final="true"]').wait_for()
                self.assertIn('실패',page.locator('#payment-status').inner_text())
                self.assertTrue(page.locator('#retry').is_visible())
                items=collect_images(page,Path(d),[])
                self.assertEqual(len(items),1)
                self.assertIn('50%',items[0]['supplied_text'])
                self.assertTrue((Path(d)/items[0]['filename']).is_file())
                skipped=collect_images(page,Path(d),[{'rule_id':'image_alt','status':'fail','target':'#offer'}])
                self.assertEqual(skipped[0]['status'],'not_run')
            finally: browser.close()

if __name__=='__main__': unittest.main()
