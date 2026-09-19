import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from app import create_app
from unittest.mock import patch

class FakeRunner:
    def __init__(self): self.gate=threading.Event(); self.gate.set(); self.fail=False; self.closed=False
    def prepare(self): pass
    def close(self): self.closed=True
    def run(self, run_id, sample, checks, output_dir, emit):
        self.gate.wait(3)
        if self.fail: raise RuntimeError('secret-token-not-for-client')
        output_dir.mkdir(parents=True,exist_ok=True)
        (output_dir/'screen.png').write_bytes(b'png')
        return {'status':'complete','rules':{'status':'complete','findings':[]},
            'audio':{'status':'complete','verdict':'pass' if sample['final_audio'] else 'fail'},
            'alt_text':{'status':'not_run','items':[]}}

class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.runner=FakeRunner()
        self.client=TestClient(create_app(self.runner,Path(self.temp.name)))
        self.client.__enter__()
    def tearDown(self):
        self.runner.gate.set(); self.client.__exit__(None,None,None); self.temp.cleanup()
    def idle(self):
        for _ in range(100):
            s=self.client.get('/api/state').json()
            if not s['busy']: return s
            time.sleep(.01)
        self.fail('worker remained busy')
    def prepare(self):
        self.assertEqual(self.client.post('/api/prepare').status_code,202); self.idle()
    def test_validation_and_busy_conflicts(self):
        self.assertEqual(self.client.post('/api/run',json={'checks':['audio']}).status_code,409)
        self.prepare()
        for checks in [[],['unknown'],['audio','audio']]:
            self.assertEqual(self.client.post('/api/run',json={'checks':checks}).status_code,422)
        self.runner.gate.clear()
        self.assertEqual(self.client.post('/api/run',json={'checks':['audio']}).status_code,202)
        for route in ['run','fix','reset','close','prepare']:
            self.assertEqual(self.client.post('/api/'+route,json={'checks':['audio']}).status_code,409)
    def test_fix_retest_and_artifacts_are_independent(self):
        self.prepare()
        self.assertEqual(self.client.post('/api/fix').status_code,409)
        one=self.client.post('/api/run',json={'checks':['audio']}).json()['run_id']
        self.assertTrue(self.idle()['can_fix'])
        self.assertEqual(self.client.post('/api/fix').status_code,200)
        two=self.client.post('/api/run',json={'checks':['audio']}).json()['run_id']
        state=self.idle(); self.assertNotEqual(one,two)
        self.assertEqual(state['runs'][0]['audio']['verdict'],'pass')
        self.assertFalse(state['can_fix'])
        self.assertEqual(self.client.get('/artifacts/'+one+'/screen.png').status_code,200)
        self.assertEqual(self.client.get('/artifacts/'+one+'/config.json').status_code,404)
        self.assertEqual(self.client.get('/artifacts/not-a-run/screen.png').status_code,404)
        self.assertEqual(self.client.post('/api/reset').status_code,200)
        self.assertEqual(len(self.client.get('/api/state').json()['runs']),2)
    def test_home_page_assets_are_served(self):
        import re
        page=self.client.get('/')
        self.assertEqual(page.status_code,200)
        for source in re.findall(r'(?:src|href)="([^" ]+\.(?:js|css))"',page.text):
            url=source if source.startswith('/') else '/'+source
            self.assertEqual(self.client.get(url).status_code,200,url)

    def test_directory_failure_releases_job_lock(self):
        self.prepare()
        with patch('app.Path.mkdir',side_effect=PermissionError('disk unavailable')):
            self.assertEqual(self.client.post('/api/run',json={'checks':['audio']}).status_code,202)
            state=self.idle()
        self.assertEqual(state['runs'][0]['status'],'error')
        self.assertFalse(state['busy'])
        self.assertEqual(self.client.post('/api/reset').status_code,200)

    def test_error_is_sanitized_and_releases_lock(self):
        self.prepare(); self.runner.fail=True
        self.client.post('/api/run',json={'checks':['audio']})
        state=self.idle(); self.assertEqual(state['runs'][0]['status'],'error')
        self.assertNotIn('secret-token',json.dumps(state))
        self.assertEqual(self.client.post('/api/close').status_code,202)
        self.assertFalse(self.idle()['prepared'])

if __name__=='__main__': unittest.main()
