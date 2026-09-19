"""One local operator, one active job; reports survive sandbox cleanup."""
import copy
import json
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, field_validator

ROOT = Path(__file__).resolve().parent

class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    checks: list[Literal['rules','audio','alt_text']]
    @field_validator('checks')
    @classmethod
    def validate_checks(cls, value):
        if not value or len(set(value)) != len(value):
            raise ValueError('Choose at least one check without duplicates')
        return value


def empty_sections():
    base = {'status':'not_run','error':None,'elapsed_ms':None}
    return {'rules':{**base,'findings':[]},
        'audio':{**base,'transcript':None,'verdict':None,'summary':None,'provider':None,'model':None,'checks':[]},
        'alt_text':{**base,'items':[]}}


def create_app(runner=None, runtime=None):
    if runner is None:
        from runner import DaytonaRunner
        runner = DaytonaRunner()
    runtime = Path(runtime or ROOT/'.runtime'/'runs')
    runtime.mkdir(parents=True,exist_ok=True)
    lock = threading.Lock()
    # ponytail: single local operator; per-user state only if multi-user support is needed.
    pool = ThreadPoolExecutor(max_workers=1)
    state = {'busy':False,'prepared':False,'stage':'대기','error':None,'revision':0,
             'can_fix':False,'current_run_id':None,'runs':[]}
    sample = {'final_audio':False}

    def refresh_fix():
        state['can_fix'] = not state['busy'] and not sample['final_audio'] and any(
            r['revision']==state['revision'] and r['audio'].get('status')=='complete'
            and r['audio'].get('verdict')=='fail' for r in state['runs'])

    def emit(stage):
        with lock: state['stage']=stage

    def reserve():
        if state['busy']: raise HTTPException(409,'검사가 진행 중입니다.')
        state.update(busy=True,can_fix=False,error=None)

    def environment_job(action):
        try:
            getattr(runner,action)()
            with lock:
                state['prepared']=action=='prepare'
                state['stage']='환경 준비 완료' if action=='prepare' else '환경 종료 완료'
        except Exception as exc:
            with lock:
                state['error']='환경 작업 실패 ('+type(exc).__name__+')'
                state['stage']='환경 작업 오류'
        finally:
            with lock: state['busy']=False; refresh_fix()

    def run_job(record, sample_snapshot, checks):
        started=time.monotonic()
        folder=runtime/record['run_id']
        try:
            folder.mkdir()
            result=runner.run(record['run_id'],sample_snapshot,checks,folder,emit)
            with lock:
                for name in ['rules','audio','alt_text']:
                    record[name].update(result.get(name,{}))
                record['status']=result.get('status','error')
                record['error']=result.get('error')
                for name in ['sandbox_id','observation_seconds']:
                    if name in result: record[name]=result[name]
        except Exception as exc:
            with lock:
                record['status']='error'
                record['error']='검사 실행 실패 ('+type(exc).__name__+')'
                for name in checks:
                    if record[name]['status']=='running':
                        record[name].update(status='error',error=record['error'])
        finally:
            with lock:
                record['elapsed_ms']=round((time.monotonic()-started)*1000)
                for name,filename in [('screen','screen.png'),('recording','recorded.wav')]:
                    if (folder/filename).is_file():
                        record['artifacts'][name]='/artifacts/'+record['run_id']+'/'+filename
                record['artifacts']['result']='/artifacts/'+record['run_id']+'/result.json'
                try:
                    (folder/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                except OSError:
                    record['status']='error'; record['error']='검사 결과 저장 실패'
                    record['artifacts']['result']=None
                state.update(busy=False,stage='검사 완료' if record['status']=='complete' else '일부 검사 또는 실행 오류')
                refresh_fix()

    @asynccontextmanager
    async def lifespan(app):
        yield
        pool.shutdown(wait=True)
        try: runner.close()
        except Exception: pass

    app=FastAPI(title='A11yChecker',lifespan=lifespan)

    @app.get('/api/state')
    def get_state():
        with lock: return copy.deepcopy(state)

    @app.post('/api/prepare',status_code=202)
    def prepare():
        with lock: reserve(); state['stage']='Daytona 환경 준비 중'
        pool.submit(environment_job,'prepare')
        return {'accepted':True}

    @app.post('/api/close',status_code=202)
    def close():
        with lock: reserve(); state['stage']='Daytona 환경 종료 중'
        pool.submit(environment_job,'close')
        return {'accepted':True}

    @app.post('/api/run',status_code=202)
    def run(body: RunRequest):
        with lock:
            if not state['prepared']: raise HTTPException(409,'환경을 먼저 준비해 주세요.')
            reserve()
            run_id=uuid.uuid4().hex
            record={'run_id':run_id,'revision':state['revision'],'status':'running','elapsed_ms':None,
                'error':None,'artifacts':{'screen':None,'recording':None,'result':None},**empty_sections()}
            for name in body.checks: record[name]['status']='running'
            state['runs'].insert(0,record)
            state.update(current_run_id=run_id,stage='검사 시작')
            sample_snapshot=dict(sample)
        pool.submit(run_job,record,sample_snapshot,list(body.checks))
        return {'run_id':run_id}

    @app.post('/api/fix')
    def fix():
        with lock:
            if state['busy'] or not state['can_fix']: raise HTTPException(409,'현재 실행의 음성 누락을 먼저 확인해 주세요.')
            sample['final_audio']=True; state['revision']+=1; refresh_fix()
            return {'revision':state['revision']}

    @app.post('/api/reset')
    def reset():
        with lock:
            if state['busy']: raise HTTPException(409,'검사가 진행 중입니다.')
            sample['final_audio']=False; state['revision']+=1; refresh_fix()
            return {'revision':state['revision']}

    @app.get('/artifacts/{run_id}/{filename}')
    def artifact(run_id: str, filename: str):
        if not re.fullmatch(r'[a-f0-9]{32}',run_id) or not re.fullmatch(r'(screen\.png|recorded\.wav|result\.json|rules\.json|image-\d+\.png)',filename):
            raise HTTPException(404)
        path=runtime/run_id/filename
        if not path.is_file() or path.is_symlink(): raise HTTPException(404)
        return FileResponse(path)

    @app.get('/')
    def index():
        path=ROOT/'static'/'index.html'
        if not path.exists(): raise HTTPException(503,'UI 통합 대기 중입니다. /docs 에서 API를 확인할 수 있습니다.')
        return FileResponse(path)

    app.mount('/static',StaticFiles(directory=str(ROOT/'static'),check_dir=False),name='static')
    return app
