"""Remote evidence collection. No AI credentials or answer-based judgments."""
import functools
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright


def selector(element):
    return element.evaluate('''el => {
      if (el.id) return '#' + CSS.escape(el.id);
      const parts=[];
      for(let n=el;n && n.nodeType===1;n=n.parentElement) {
        let part=n.tagName.toLowerCase();
        const siblings=n.parentElement ? [...n.parentElement.children].filter(x=>x.tagName===n.tagName) : [];
        if(siblings.length>1) part+=':nth-of-type('+(siblings.indexOf(n)+1)+')';
        parts.unshift(part);
      }
      return parts.join(' > ');
    }''')


def collect_images(page, folder, findings):
    missing=[f['target'] for f in findings if f.get('rule_id')=='image_alt' and f.get('status')=='fail']
    items=[]; captured=0
    for element in page.locator('img').all():
        if not element.is_visible(): continue
        target=selector(element)
        data=element.evaluate('''el => ({alt:el.getAttribute('alt'), aria:el.getAttribute('aria-label'),
          referenced:(el.getAttribute('aria-labelledby')||'').split(/\\s+/).map(id=>document.getElementById(id)?.textContent||'').join(' ').trim(),
          context:el.parentElement.innerText.slice(0,1200), loaded:el.complete && el.naturalWidth>0})''')
        text=data['referenced'] or data['aria'] or data['alt'] or ''
        item={'target':target,'supplied_text':text,'context':data['context'],'status':'not_run','filename':None}
        excluded=any(element.evaluate('(el, s) => el.matches(s)',s) for s in missing)
        if excluded: item['summary']='기본 검사에서 대안 누락 확인; 중복 의미 검사는 생략했습니다.'
        elif captured>=3: item['summary']='이번 실행의 이미지 검사 한도 3개를 초과했습니다.'
        elif not data['loaded']: item.update(status='error',summary='이미지가 로딩되지 않았습니다.')
        else:
            try:
                filename='image-'+str(captured)+'.png'
                element.screenshot(path=str(folder/filename))
                item.update(status='captured',filename=filename)
                captured+=1
            except Exception: item.update(status='error',summary='이미지를 캡처하지 못했습니다.')
        items.append(item)
    return items


def run(request, root):
    folder=root/'runs'/request['run_id']; folder.mkdir(parents=True)
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(root/'sample')))
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    observed={'rules':{'status':'not_run','findings':[]},'images':[],'audio_error':None}
    recording=None
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,ignore_default_args=['--mute-audio'],
                args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
            try:
                page=browser.new_page(viewport={'width':1000,'height':760},device_scale_factor=1)
                audio='audio' in request['checks'] and request['audio_ready']
                query='?audio='+str(int(audio))+'&final='+str(int(request['final_audio']))
                page.goto('http://127.0.0.1:'+str(server.server_port)+'/'+query,wait_until='networkidle')
                if audio:
                    audio_started=time.monotonic()
                    recording=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','pulse','-i','a11y.monitor',
                        '-ac','1','-ar','16000','-c:a','pcm_s16le',str(folder/'recorded.wav')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                    time.sleep(.5)
                elif 'audio' in request['checks']: observed['audio_error']='샘플 음성 자산 준비 실패'
                page.locator('#pay').click()
                page.locator('#payment-status[data-final="true"]').wait_for(timeout=15000)
                if audio: page.wait_for_timeout(8000)
                page.screenshot(path=str(folder/'screen.png'),full_page=True)
                observed['screen_text']=page.locator('body').inner_text()
                if recording:
                    try:
                        _,errors=recording.communicate(b'q',timeout=10)
                        if recording.returncode!=0: observed['audio_error']='녹음 프로세스 오류'
                    except subprocess.TimeoutExpired:
                        recording.kill(); recording.communicate(); observed['audio_error']='녹음 종료 시간 초과'
                    recording=None
                    observed['audio_capture_ms']=round((time.monotonic()-audio_started)*1000)
                if 'rules' in request['checks']:
                    started=time.monotonic()
                    try:
                        import rules
                        result=rules.scan(page)
                        observed['rules']={'status':'complete','error':None,'elapsed_ms':round((time.monotonic()-started)*1000),'findings':result['findings']}
                        (folder/'rules.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                    except Exception as exc:
                        observed['rules']={'status':'error','error':'기본 검사 실행 오류 ('+type(exc).__name__+')','findings':[]}
                if 'alt_text' in request['checks']:
                    try: observed['images']=collect_images(page,folder,observed['rules']['findings'])
                    except Exception: observed['images_error']='이미지 증거 수집 실패'
            finally: browser.close()
    finally:
        if recording: recording.kill(); recording.communicate()
        server.shutdown(); server.server_close()
    (folder/'observed.json').write_text(json.dumps(observed,ensure_ascii=False),encoding='utf-8')
    with zipfile.ZipFile(folder/'evidence.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in folder.iterdir():
            if path.name!='evidence.zip': archive.write(path,path.name)

if __name__=='__main__':
    config_path=Path(sys.argv[1])
    run(json.loads(config_path.read_text()),config_path.parent)
