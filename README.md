# A11yChecker

키오스크 웹앱의 화면에는 있지만 실제 음성에는 빠진 중요한 안내를 찾는 접근성 QA MVP.

## 현재 구현 상태

- 리드 구현: FastAPI 실행 제어, Daytona Chromium 실행, 실제 PulseAudio 출력 녹음, WAV 전사, 음성·이미지 설명 의미 판정, 샘플 수정 후 새 실행.
- 외부 담당: 자체 규칙 5개와 결과 UI. 해당 브랜치 통합 전에는 `/docs`에서 API를 사용할 수 있다. 미구현 규칙은 통과로 가장하지 않고 오류로 남는다.
- `main`에 초기 리드 구현이 병합되었으며 최신 검증 수정은 `lead/integration`에 있다. 완성된 전체 MVP라는 의미는 아니다.

## 실행

Python 3.11 이상 권장. Windows PowerShell 예시:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
# .env에 DAYTONA_API_KEY, OPENAI_API_KEY를 직접 설정
.\start.ps1 -Python .\.venv\Scripts\python.exe
```

`http://127.0.0.1:8090`을 연다. 외부 `.env`를 사용할 때는 `start.ps1 -EnvFile 경로` 또는 `A11Y_ENV_FILE`을 설정한다. 키 값은 Git에 넣지 않는다. Daytona API URL/target은 계정 설정에 맞춘다. 모델은 명시적으로 gpt-4.1-mini(의미), whisper-1(전사), tts-1(시연 음성)을 사용한다. Nosana 키는 선택이며 현재 의미 판정에는 사용하지 않는다.

Daytona 준비에는 Linux 패키지와 Chromium 환경 설치가 포함된다. 환경 준비를 먼저 끝내고 시연을 시작한다. 실제 클라우드·모델 호출은 비용을 소비한다. 한 번에 하나의 작업만 실행한다.

UI 통합 전 API 순서:

1. POST `/api/prepare`, GET `/api/state`에서 busy=false, prepared=true 확인.
2. POST `/api/run`에 `{"checks":["audio","alt_text"]}` 전달. 규칙 통합 후 rules를 추가한다.
3. 음성 fail 확인 → POST `/api/fix` → 새 POST `/api/run`.
4. POST `/api/close`로 소유 샌드박스 삭제. 앱 정상 종료도 정리를 시도한다.

실행별 원본 화면·녹음·결과는 `.runtime/runs/<run_id>/`에 저장된다. 초기화와 환경 종료는 이전 증거를 지우지 않는다. 프로세스 재시작 시 UI 이력은 초기화되며 파일은 남는다. 비정상 강제 종료 후에는 `.runtime/sandbox.json`의 ID로 Daytona 콘솔에서 남은 환경을 확인한다. 샌드박스 TTL은 60분, 자동 정지는 10분이다.

## 검증

```powershell
python -m unittest discover -s tests -v
# 실제 API·Daytona 사용. 실제 fail → fix → pass, 이미지 정상/결함, 삭제까지 검증
python tests/live_demo.py --checks audio,alt_text
```

로컬 브라우저 테스트에는 Chromium이 필요하다. 현재 Windows 테스트는 설치된 Chrome을 사용한다. 원격 제품 브라우저는 Daytona의 Playwright 이미지에서 실행된다.

2026-09-19 수정 후 실제 리드 리허설의 새 브라우저 2회 실행 결과:

| 실행 | 실제 녹음의 전사 | 음성 판정 | 실행 전체 시간 |
|---|---|---|---|
| 결함 | 결제를 처리 중입니다. | fail | 27.047초 |
| 수정 | 결제를 처리 중입니다. 결제가 완료되지 않았습니다. 다시 시도 버튼을 눌러주세요. | pass | 24.703초 |

위 시간은 준비 완료 뒤 음성+이미지 검사 실행이며 환경 준비 시간은 제외한다. 성능 보장이나 반복 평균이 아니다. 서로 다른 run_id와 녹음 SHA256을 확인했다. 올바른 할인 이미지 설명은 pass, 잘못된 할인율·시간 설명은 fail을 확인했다. 테스트 샌드박스 삭제까지 완료했다. 로컬 증거 요약은 `.runtime/live-summary.json`; 개인정보·실행 자료는 저장소에 올리지 않는다.

리드 테스트 15개가 통과했다. 독립 코드 리뷰에서 발견한 실행 잠금·근거 검증·장식 이미지 빈 alt 처리와 시간 집계 문제를 재현 테스트로 수정했다. 외부 규칙·UI 통합은 별도 확인 대상이다.

두 번째 실제 실행에서 모델이 화면에 보이는 정보를 음성으로 전달된 것으로 잘못 인정하는 오판을 관찰했다. 화면은 요구 정보, 전사문은 전달 근거로 명확히 구분하도록 지시를 수정했다. 보존한 실제 결함/정상 녹음을 각각 3회 재판정해 총 6/6 기대 결과를 확인했다. 이는 제한된 회귀 검증이며 모델의 일반 정확도나 무오류를 보장하지 않는다. 별도 불완전 화면·손상 전사 합성 사례에서 판단 보류 대신 fail 또는 유효하지 않은 응답이 발생했다. 따라서 불명확 사례의 자동 분류는 추가 검증이 필요하다. 무효 응답은 실행 오류로 남기며 통과로 처리하지 않는다. 재생 검증 명령은 `python tests/live_model_regression.py --bad-run <결함ID> --good-run <정상ID>`이고 해당 로컬 증거 파일이 필요하다.

## 범위와 한계

- 시연 입력은 저장소의 고정 샘플 웹앱이다. 임의 사이트 크롤링·로그인·실물 키오스크 하드웨어를 검사하지 않는다.
- 화면의 결제 실패 뒤 8초간 음성 출력을 관찰한다. 법정 응답 제한이나 사람의 반응 시간을 의미하지 않는다.
- 실제 녹음을 ASR로 전사하므로 전사 오류가 판단에 영향을 줄 수 있다. 사용자는 녹음·화면·근거를 직접 확인한다. 무음·전사 실패를 통과로 처리하지 않는다.
- AI 판정은 개발 QA 보조이며 공인 인증·전체 접근성 준수를 보장하지 않는다. Deque 제품과 직접 동일 조건 비교를 수행한 것은 아니다.
- 기본 규칙은 AI 호출 없이 처리한다. 복잡한 대비는 확인 필요, 16px 미만은 제품 권장값 주의다. 외부 접근성 검사 엔진은 사용하지 않는다.

## 협업 문서

- [규칙·파일 소유권](AGENTS.md)
- [설계](docs/superpowers/specs/2026-09-19-accessibility-audio-qa-design.md)
- [계획·API 계약·에이전트 작업 지시](docs/superpowers/plans/2026-09-19-accessibility-audio-qa.md#git-협업-실행-계약)
- 구현 참고: [OpenAI 음성 생성 API](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create), [전사 API](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create), [Chat API](https://developers.openai.com/api/reference/resources/chat).
