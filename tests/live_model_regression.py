"""Replay observed evidence against the live model after a prompt regression."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit import judge
from runner import load_config

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bad-run',required=True)
    parser.add_argument('--good-run',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    rows=[]
    for run_id, expected in [(args.bad_run,'fail'),(args.good_run,'pass')]:
        folder=root/'.runtime'/'runs'/run_id
        saved=json.loads((folder/'result.json').read_text(encoding='utf-8'))
        observed=json.loads((folder/'observed.json').read_text(encoding='utf-8'))
        for attempt in range(3):
            result=judge((folder/'screen.png').read_bytes(),saved['audio']['transcript'],'audio',
                '최종 화면 후 8초까지 관찰. 화면 텍스트: '+observed['screen_text'],load_config())
            rows.append({'source_run_id':run_id,'attempt':attempt,'result':result})
            print(json.dumps({'expected':expected,'actual':result['verdict'],'checks':result['checks']},ensure_ascii=False),flush=True)
            assert result['verdict']==expected
    (root/'.runtime'/'model-regression.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODEL REPLAY PASS 6/6; reused recorded evidence, not new browser runs.',flush=True)

if __name__=='__main__': main()
