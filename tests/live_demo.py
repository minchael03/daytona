"""Opt-in real Daytona/API rehearsal. Makes paid calls; never runs in unittest discovery."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import create_app
from runner import DaytonaRunner
from audit import judge


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--checks',default='audio,alt_text')
    args=parser.parse_args()
    checks=args.checks.split(',')
    root=Path(__file__).resolve().parents[1]
    runner=DaytonaRunner()
    observations=[]
    def wait(client,seconds=300):
        deadline=time.monotonic()+seconds; previous=None
        while time.monotonic()<deadline:
            state=client.get('/api/state').json()
            if state['stage']!=previous:
                print(state['stage'],flush=True); previous=state['stage']
            if not state['busy']: return state
            time.sleep(.5)
        raise RuntimeError('Timed out waiting for API job')
    try:
        with TestClient(create_app(runner,root/'.runtime'/'runs')) as client:
            assert client.post('/api/prepare').status_code==202
            prepared=wait(client)
            if not prepared['prepared']: raise RuntimeError(prepared['error'])
            for fixed in [False,True]:
                if fixed: assert client.post('/api/fix').status_code==200
                response=client.post('/api/run',json={'checks':checks})
                assert response.status_code==202,response.text
                state=wait(client); report=state['runs'][0]
                print(json.dumps({'run_id':report['run_id'],'status':report['status'],'audio':report['audio'],
                    'alt_text':report['alt_text'],'elapsed_ms':report['elapsed_ms']},ensure_ascii=False),flush=True)
                observations.append(report)
                expected='pass' if fixed else 'fail'
                assert report['audio']['verdict']==expected,report['audio']
                if 'alt_text' in checks:
                    assert report['alt_text']['items'][0]['verdict']=='pass',report['alt_text']
            first,second=observations
            assert first['run_id']!=second['run_id']
            hashes=[]
            for report in observations:
                folder=root/'.runtime'/'runs'/report['run_id']
                hashes.append(hashlib.sha256((folder/'recorded.wav').read_bytes()).hexdigest())
            assert hashes[0]!=hashes[1]
            folder=root/'.runtime'/'runs'/second['run_id']
            if 'alt_text' in checks:
                wrong=judge((folder/'image-0.png').read_bytes(),'모든 음료 90% 할인, 하루 종일',
                    'alt_text','카페의 할인 행사 안내 이미지',runner.config)
                assert wrong['verdict']=='fail',wrong
                (root/'.runtime'/'image-negative.json').write_text(json.dumps(wrong,ensure_ascii=False,indent=2),encoding='utf-8')
            (root/'.runtime'/'live-summary.json').write_text(json.dumps({'runs':observations,'recording_hashes':hashes},ensure_ascii=False,indent=2),encoding='utf-8')
            assert client.post('/api/close').status_code==202
            assert not wait(client)['prepared']
            print('LIVE PASS: actual audio fail -> fresh audio pass; image positive/negative; sandbox deleted.',flush=True)
    finally:
        runner.close()

if __name__=='__main__': main()
