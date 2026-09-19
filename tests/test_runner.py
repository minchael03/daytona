import io
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from runner import analyze_observation, wav_metrics

class RunnerTests(unittest.TestCase):
    def test_streaming_wav_header_uses_actual_frames(self):
        stream=io.BytesIO()
        with wave.open(stream,'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(struct.pack('<h',1000)*16000)
        raw=bytearray(stream.getvalue())
        raw[4:8]=struct.pack('<I',0xffffffff); pos=raw.find(b'data')
        raw[pos+4:pos+8]=struct.pack('<I',0xffffffff)
        stats=wav_metrics(bytes(raw))
        self.assertAlmostEqual(stats['duration_seconds'],1)
        self.assertGreater(stats['rms_dbfs'],-40)
    def test_rules_only_never_calls_models(self):
        with tempfile.TemporaryDirectory() as d, patch('runner.judge') as judge, patch('runner.transcribe') as asr:
            report=analyze_observation({'rules':{'status':'complete','findings':[]}},['rules'],Path(d),{},lambda s:None)
            self.assertEqual(report['rules']['status'],'complete')
            self.assertEqual(report['audio']['status'],'not_run')
            judge.assert_not_called(); asr.assert_not_called()
    def test_ai_error_preserves_rules_and_recording(self):
        with tempfile.TemporaryDirectory() as d, patch('runner.transcribe',side_effect=RuntimeError('private API secret')):
            folder=Path(d); (folder/'recorded.wav').write_bytes(b'wav'); (folder/'screen.png').write_bytes(b'png')
            report=analyze_observation({'rules':{'status':'complete','findings':[{'status':'fail'}]},'audio_error':None,'screen_text':'결제 실패'},['rules','audio'],folder,{},lambda s:None)
            self.assertEqual(report['status'],'partial')
            self.assertEqual(report['rules']['findings'][0]['status'],'fail')
            self.assertEqual(report['audio']['status'],'error')
            self.assertIsNone(report['audio']['verdict'])
            self.assertNotIn('private API secret',json.dumps(report))

    def test_audio_duration_includes_preparation_and_capture(self):
        with tempfile.TemporaryDirectory() as d, patch('runner.transcribe',return_value=('text',{})), patch('runner.judge',return_value={'verdict':'pass'}):
            folder=Path(d); (folder/'screen.png').write_bytes(b'png')
            report=analyze_observation({'audio_prepare_ms':2000,'audio_capture_ms':3500},['audio'],folder,{},lambda s:None)
            self.assertGreaterEqual(report['audio']['elapsed_ms'],5500)

if __name__=='__main__': unittest.main()
