"""Run a fixed sample in Daytona; analyze only observed artifacts locally."""
import io
import json
import math
import os
import struct
import time
import wave
import zipfile
from pathlib import Path
import httpx
from dotenv import dotenv_values
from audit import judge

ROOT=Path(__file__).resolve().parent


def load_config():
    values={**dotenv_values(os.environ.get('A11Y_ENV_FILE',str(ROOT/'.env'))),**os.environ}
    return {k:values[k] for k in ['DAYTONA_API_KEY','DAYTONA_API_URL','DAYTONA_TARGET','OPENAI_API_KEY','NOSANA_API_KEY'] if values.get(k)}


def wav_metrics(data):
    with wave.open(io.BytesIO(data),'rb') as source:
        width, channels, rate=source.getsampwidth(),source.getnchannels(),source.getframerate()
        frames=source.readframes(source.getnframes())
    if width!=2 or not frames: raise ValueError('Expected nonempty PCM16 WAV')
    samples=struct.unpack('<'+'h'*(len(frames)//2),frames)
    rms=math.sqrt(sum(x*x for x in samples)/len(samples))
    return {'duration_seconds':len(frames)/(width*channels*rate),
            'rms_dbfs':20*math.log10(max(rms,1)/32768)}


def speech(text, config):
    key=config.get('OPENAI_API_KEY')
    if not key: raise RuntimeError('OPENAI_API_KEY is not configured')
    response=httpx.post('https://api.openai.com/v1/audio/speech',headers={'Authorization':'Bearer '+key},
        json={'model':'tts-1','voice':'alloy','input':text,'response_format':'wav'},timeout=60)
    if response.status_code!=200: raise RuntimeError('Speech API HTTP '+str(response.status_code))
    return response.content


def transcribe(path, config):
    metrics=wav_metrics(path.read_bytes())
    if metrics['duration_seconds']<1 or metrics['rms_dbfs'] < -55:
        raise ValueError('Recording is too short or silent; manual verification needed')
    key=config.get('OPENAI_API_KEY')
    if not key: raise RuntimeError('OPENAI_API_KEY is not configured')
    with path.open('rb') as recording:
        response=httpx.post('https://api.openai.com/v1/audio/transcriptions',headers={'Authorization':'Bearer '+key},
            files={'file':('recorded.wav',recording,'audio/wav')},
            data={'model':'whisper-1','language':'ko','response_format':'json'},timeout=60)
    if response.status_code!=200: raise RuntimeError('ASR API HTTP '+str(response.status_code))
    text=response.json().get('text','').strip()
    if not text: raise ValueError('ASR produced no transcript')
    return text, metrics


def analyze_observation(observed, checks, folder, config, emit):
    from app import empty_sections
    report=empty_sections()
    if 'rules' in checks: report['rules'].update(observed.get('rules',{'status':'error','error':'규칙 결과 없음'}))
    if 'audio' in checks:
        started=time.monotonic()
        try:
            if observed.get('audio_error'): raise RuntimeError('Recording unavailable')
            emit('실제 녹음 전사 중')
            transcript,metrics=transcribe(folder/'recorded.wav',config)
            report['audio'].update(transcript=transcript,recording_metrics=metrics)
            emit('화면과 음성 의미 비교 중')
            context='최종 화면 뒤 8초까지 실제 브라우저 출력을 관찰했습니다. 화면 텍스트: '+observed.get('screen_text','')
            result=judge((folder/'screen.png').read_bytes(),transcript,'audio',context,config)
            report['audio'].update(result,status='complete')
        except Exception as exc:
            report['audio'].update(status='error',error='음성 증거 처리 실패 ('+type(exc).__name__+')')
        report['audio']['elapsed_ms']=round((time.monotonic()-started)*1000)+observed.get('audio_prepare_ms',0)+observed.get('audio_capture_ms',0)
    if 'alt_text' in checks:
        started=time.monotonic(); items=[]
        for candidate in observed.get('images',[]):
            item={'target':candidate['target'],'image_url':None,'supplied_text':candidate.get('supplied_text',''),
                  'status':'not_run','error':None,'verdict':None,'summary':candidate.get('summary'),
                  'provider':None,'model':None,'elapsed_ms':None,'checks':[]}
            if candidate.get('filename'):
                item['image_url']='/artifacts/'+folder.name+'/'+candidate['filename']
            if candidate['status']=='captured':
                item_started=time.monotonic()
                try:
                    emit('이미지 설명 의미 비교 중')
                    item.update(judge((folder/candidate['filename']).read_bytes(),item['supplied_text'],
                        'alt_text',candidate.get('context',''),config),status='complete')
                except Exception as exc:
                    item.update(status='error',error='이미지 의미 처리 실패 ('+type(exc).__name__+')')
                item['elapsed_ms']=round((time.monotonic()-item_started)*1000)
            elif candidate['status']=='error':
                item.update(status='error',error='이미지 캡처 실패')
            items.append(item)
        report['alt_text'].update(status='error' if observed.get('images_error') or any(i['status']=='error' for i in items) else 'complete',
            error='일부 이미지 증거를 처리하지 못했습니다.' if observed.get('images_error') or any(i['status']=='error' for i in items) else None,
            items=items,elapsed_ms=round((time.monotonic()-started)*1000))
    states=[report[c]['status'] for c in checks]
    report['status']='complete' if all(s=='complete' for s in states) else 'partial' if 'complete' in states else 'error'
    report['observation_seconds']=8 if 'audio' in checks else None
    return report


class DaytonaRunner:
    def __init__(self, config=None):
        self.config=load_config() if config is None else config
        self.client=None; self.sandbox=None
        self.runtime=ROOT/'.runtime'; self.runtime.mkdir(exist_ok=True)

    def prepare(self):
        if self.sandbox is not None: return
        from daytona import Daytona, DaytonaConfig, CreateSandboxFromImageParams
        if not self.config.get('DAYTONA_API_KEY'): raise RuntimeError('DAYTONA_API_KEY is not configured')
        options={'api_key':self.config['DAYTONA_API_KEY']}
        for key,field in [('DAYTONA_API_URL','api_url'),('DAYTONA_TARGET','target')]:
            if self.config.get(key): options[field]=self.config[key]
        self.client=Daytona(DaytonaConfig(**options))
        self.sandbox=self.client.create(CreateSandboxFromImageParams(
            image='mcr.microsoft.com/playwright/python:v1.63.0-noble',os_user='root',public=False,
            ephemeral=True,ttl_minutes=60,auto_stop_interval=10,labels={'project':'a11y-checker'}),timeout=180)
        (self.runtime/'sandbox.json').write_text(json.dumps({'id':self.sandbox.id}),encoding='utf-8')
        try:
            self._exec('mkdir -p /tmp/a11y/sample /tmp/a11y/runs && apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq pulseaudio ffmpeg fonts-noto-cjk >/tmp/a11y-install.log 2>&1 && python3 -m pip install -q playwright==1.63.0',180)
            self._exec('pulseaudio --start --exit-idle-time=-1 && pactl load-module module-null-sink sink_name=a11y && pactl set-default-sink a11y',30)
        except Exception:
            self.close()
            raise

    def _exec(self,command,timeout=120):
        result=self.sandbox.process.exec(command,timeout=timeout)
        if result.exit_code!=0:
            raise RuntimeError('Daytona command failed (exit '+str(result.exit_code)+')')
        return result

    def run(self,run_id,sample,checks,output_dir,emit):
        if self.sandbox is None: raise RuntimeError('Prepare environment first')
        emit('Daytona에 검사 코드와 샘플 전송 중')
        self.sandbox.fs.upload_file(str(ROOT/'worker.py'),'/tmp/a11y/worker.py')
        if (ROOT/'rules.py').exists(): self.sandbox.fs.upload_file(str(ROOT/'rules.py'),'/tmp/a11y/rules.py')
        for path in (ROOT/'sample').iterdir():
            if path.is_file(): self.sandbox.fs.upload_file(str(path),'/tmp/a11y/sample/'+path.name)
        audio_ready=True; audio_prepare_ms=0
        if 'audio' in checks:
            emit('샘플 음성 자산 준비 중')
            audio_started=time.monotonic()
            assets=self.runtime/'assets'; assets.mkdir(exist_ok=True)
            try:
                for name,text in [('processing.wav','결제를 처리 중입니다.'),('failure.wav','결제가 완료되지 않았습니다. 다시 시도 버튼을 눌러 주세요.')]:
                    path=assets/name
                    if not path.exists(): path.write_bytes(speech(text,self.config))
                    self.sandbox.fs.upload_file(str(path),'/tmp/a11y/sample/'+name)
            except Exception:
                audio_ready=False
            audio_prepare_ms=round((time.monotonic()-audio_started)*1000)
        request={'run_id':run_id,'checks':checks,'final_audio':bool(sample['final_audio']),'audio_ready':audio_ready}
        self.sandbox.fs.upload_file(json.dumps(request).encode(),'/tmp/a11y/request.json')
        emit('Daytona 브라우저 실행·실제 출력 관찰 중')
        self._exec('PULSE_SINK=a11y python3 /tmp/a11y/worker.py /tmp/a11y/request.json',120)
        archive=self.sandbox.fs.download_file('/tmp/a11y/runs/'+run_id+'/evidence.zip')
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for name in bundle.namelist():
                if Path(name).name != name or name not in {'observed.json','screen.png','recorded.wav','rules.json'} and not (name.startswith('image-') and name.endswith('.png')):
                    raise ValueError('Unexpected artifact path')
                (output_dir/name).write_bytes(bundle.read(name))
        observed=json.loads((output_dir/'observed.json').read_text(encoding='utf-8'))
        observed['audio_prepare_ms']=audio_prepare_ms
        result=analyze_observation(observed,checks,output_dir,self.config,emit)
        result['sandbox_id']=self.sandbox.id
        return result

    def close(self):
        if self.sandbox is not None:
            self.client.delete(self.sandbox,timeout=60,wait=True)
            self.sandbox=None
            (self.runtime/'sandbox.json').unlink(missing_ok=True)
