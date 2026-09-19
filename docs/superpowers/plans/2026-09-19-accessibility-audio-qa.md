# 화면·음성 접근성 QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Follow the Git collaboration ownership below; the lead integrates and obtains independent final review. Track the checkboxes below.

**Goal:** 5가지 자체 기본 검사와 AI 음성·이미지 의미 검사를 연결하고, 결제 실패 안내 누락 → 실제 수정 → 새 녹음 재검사를 시연하는 MVP.

**Architecture:** FastAPI + 정적 UI, 일반 코드가 실행 순서와 선택된 검사를 제어한다. Daytona에서 Chromium·DOM/CSS·실제 출력 음성을 관찰하고, 규칙 검사와 필요한 AI 판정을 분리 저장한다.

**Tech Stack:** Python, FastAPI 0.141.1, Uvicorn 0.53.0, httpx 0.28.1, python-dotenv 1.2.3, Daytona 0.214.0, Playwright 1.63.0, PulseAudio, FFmpeg. 표준 unittest. 검사 엔진·에이전트 프레임워크는 추가하지 않는다.

**Spec:** [현재 설계](../specs/2026-09-19-accessibility-audio-qa-design.md)

## 이전 범위와 시간 기록 (최신 시간과 소유권은 Git 계약 참조)

사용자 지시에 따라 8개 후보에서 5개로 축소했다: 이미지 텍스트 대안, 단색 대비, 폼 레이블, 버튼 이름, 글자 크기 주의. 링크 이름·문서 언어·문서 제목은 제외한다. AI는 음성 의미와 대체 텍스트 의미 두 작업만 맡는다. 기본 검사는 데모의 주인공이 아니므로 별도 화면·통계·자동 수정 기능을 만들지 않는다.

목표: 14:23부터 약 1시간 안에 연결된 MVP. 계획 확인 뒤 즉시 구현한다. 기본 검사·계약 15분, 실제 Daytona 흐름 20분, API·UI 15분, 리허설·독립 리뷰·수정 10분을 목표로 한다. 이는 보장이 아니라 작업 예산이다. 시간이 밀리면 장식·발표 추가 자료·선택 스폰서 통합을 줄이고 실제 녹음과 재검증을 유지한다.

## Global Constraints

- 제품 코드는 2026-09-19 14:00 KST 이후 새로 작성한다. 사전 실험 코드를 제출용으로 복사하지 않는다.
- axe-core, Lighthouse, WAVE 등 외부 접근성 엔진을 설치·호출하지 않는다.
- 모델 키 없이 규칙 검사만 가능해야 한다. 규칙 전용 실행에서 TTS·ASR·LLM 호출은 0회다.
- 음성 관찰은 최종 화면 등장 후 8초. 법정 제한 시간이나 사람의 반응 시간으로 설명하지 않는다.
- 모델에는 정답·샘플 모드·수정 여부·TTS 원문을 주지 않는다.
- 복잡한 CSS 대비는 확인 필요. 16px 미만은 제품 권장값 경고이며 WCAG 위반으로 표시하지 않는다.
- 음성·이미지 모델 실패가 규칙 결과를 없애거나 통과로 바꾸지 않는다.
- 한 번에 한 실행. 실행 중 수정·초기화·종료 요청은 409로 거절한다.
- 매 실행 새 ID·브라우저·녹음·판정. 이전 증거를 덮어쓰지 않는다.
- 실제 사용한 엔진·모델·시간만 표시한다. 전체 접근성 점수와 공인 인증 통과 문구는 없다.
- 키는 서버·작업자 전용이며 UI·로그·공개 결과·Git에 남기지 않는다.
- 데이터베이스·로그인·임의 사이트 크롤러·실물 장치·자동 키 순환은 없다.

## Review Focus

1. ARIA 이름·label·이미지 이름이 있는 버튼을 빈 버튼으로 오탐하지 않는다. Task 1의 정상/결함 DOM 사례로 확인.
2. 빈 alt와 복잡한 배경은 무조건 실패·통과로 바꾸지 않는다. Task 1 규칙 테스트와 Task 2 이미지 판정으로 확인.
3. 규칙 전용 실행은 모델 호출 0회, AI 실패 시 규칙 결과 보존. Task 2 실행 분기 검사.
4. 중복 실행·실행 중 수정은 기존 작업을 건드리지 않는다. Task 3 동시성 검사.
5. 수정 후 전사·화면·판정은 새 실행의 결과다. Task 3 실제 전후 파일 해시·ID 검사.

## 실행 환경과 사전 확인

프로젝트 위치: `C:/Users/gram/Documents/Codex/2026-09-19/ai-superpowers-brainstorming-https-luma-com/accessibility-qa/`. 상위는 Git 저장소가 아니므로 제품 폴더만 새 저장소로 초기화한다. 기존 D:/src/hackathon 제품 코드는 수정하지 않는다. 적용 지침: `D:/src/hackathon/AGENTS.md`.

기존 실행 파일: `D:/src/hackathon/kiosk-localizer/.venv/Scripts/python.exe`. 위 라이브러리가 설치돼 있다. pytest는 없으므로 unittest를 쓴다. Chrome·Edge 설치 확인 완료.

연결 설정은 `D:/src/hackathon/kiosk-localizer/.env`에서 DAYTONA_API_KEY, DAYTONA_API_URL, DAYTONA_TARGET, OPENAI_API_KEY, NOSANA_API_KEY만 읽는다. 값은 출력하지 않는다. 기존 프로젝트의 모델·추론 강도 설정은 재사용하지 않는다.

Daytona 실제 출력 녹음→한국어 ASR은 사전 1회 성공했다. `work/daytona-audio/output/summary.json`과 WAV·PNG에 기록돼 있으며 샌드박스는 삭제했다. 전체 37.94초는 사전 실험값이다. 이번 제품의 처리 시간으로 발표하지 않는다.

Nosana는 선택 가산점이다. 인증·모델 목록·잔액 조회 HTTP 200, 현재 잔액 10크레딧. 후보 모델 `qwen/qwen3.8-27b`의 이미지 지원·JSON 응답은 미확인이다. 핵심 구현을 막지 않도록 초기 연결 검증에 최대 5분만 사용하고 실패하면 OpenAI로 간다. OpenAI 기준 모델은 이미지 입력을 지원하는 gpt-4.1-mini, TTS tts-1, ASR whisper-1이다. 두 공급자의 의미 판정은 실제로 검증해야 한다.

현재 PDF 사전 자료 2장: `output/pdf/accessibility-qa-prelaunch.pdf`. 결과 페이지는 실제 제품 증거가 확보된 후 추가한다. 시연 대본은 설계 문서가 원본이다.

## 파일과 계약

| 파일 | 책임 |
|---|---|
| rules.py | DOM·스타일 수집, 5개 규칙, 명확한 근거와 확인 필요 결과 |
| audit.py | 음성/이미지 판정 요청, 구조화 응답·근거 검증 |
| worker.py | 원격 샘플 실행, 브라우저·녹음·전사·선택 검사, 실행 결과 저장 |
| runner.py | Daytona 생성·업로드·준비·작업·산출물 수집·삭제 |
| app.py | FastAPI, 단일 작업 잠금, 검사·수정·초기화·종료 |
| sample/index.html, sample/offer.svg | 실제 결제 흐름, 검사할 이미지 |
| static/index.html, static/style.css, static/app.js | 한 화면에서 실행 상태·종류별 결과·실제 증거·전후 비교 |
| tests/test_rules.py, tests/test_audit.py, tests/test_app.py | 규칙·계약·분기·오류·동시성 검증 |
| tests/live_demo.py | 실제 모델·Daytona 전후 검증 |
| requirements.txt, .gitignore, start.ps1, README.md | 실행·재현 방법, 비밀·실행 결과 제외 |

- `rules.inspect_snapshot(snapshot: dict) -> list[dict]`: 항목별 rule_id, status(pass/fail/needs_review/info), target, summary, evidence. 크기 주의는 needs_review이고 basis는 product-guidance.
- `rules.scan(page) -> dict`: 관찰한 DOM 스냅샷과 findings 반환. httpx·API 키·모델 의존 없음.
- `audit.validate_result(value: dict, kind: str) -> dict`: kind=audio/alt_text. verdict=pass/fail/needs_review, summary, checks를 검증한다.
- 각 AI check: topic, status(delivered/missing/contradicted/uncertain), visual_evidence, provided_evidence, reason. audio 주제는 payment_result·next_action, alt_text는 image_description.
- `audit.judge(image: bytes, supplied_text: str, kind: str, context: str, config: dict) -> dict`: 실제 공급자·모델·시간 포함 결과. API 오류·잘못된 응답은 실행 오류.
- `DaytonaRunner.prepare()`, `run(run_id, sample, checks, output_dir, emit)`, `close()`: app.py에서 호출. prepare는 브라우저·녹음 실행 환경만 준비하며 모델 호출 없음.
- worker 실행 산출물: screen.png, recorded.wav(음성 선택 시), rules.json, result.json, 이미지 캡처. 결과 최상위 rules/audio/alt_text를 분리하고 개별 오류 상태를 보존.

## Task 1: 자체 기본 검사와 AI 판정 계약

- [ ] 제품 폴더·독립 Git 저장소 초기화. requirements와 .gitignore를 함께 만든다. 런타임·키·캐시를 제외한다.
- [ ] 먼저 아래 핵심 수치와 DOM 사례를 테스트로 작성해 RED를 확인한다.

```python
self.assertAlmostEqual(contrast_ratio((0, 0, 0), (255, 255, 255)), 21)
self.assertAlmostEqual(contrast_ratio((90, 90, 90), (90, 90, 90)), 1)
self.assertEqual(required_contrast(24, 400), 3)
self.assertEqual(required_contrast(16, 400), 4.5)
self.assertFalse(meets_contrast(4.499, 4.5))
```

`contrast_ratio`, `required_contrast`, `meets_contrast`는 rules.py의 순수 함수다. DOM 사례는 alt 누락/빈 alt/ARIA 이름, 연결된 label/placeholder만 있음, 이미지 alt로 이름을 가진 버튼/빈 버튼, 단색 배경/gradient, 작은 글자를 포함한다. 테스트는 실제 Chromium에 HTML fixture를 로딩해 collect 결과도 확인한다.

- [ ] DOM 수집은 Playwright page.evaluate와 getComputedStyle을 사용한다. 대조는 일반 텍스트의 단색 전경·배경만 확정하며 투명 조상, gradient, filter, opacity, shadow 등은 보수적으로 보류한다. 이름은 ARIA·label·콘텐츠·이미지 alt·title·native value를 고려하고 확정할 수 없는 경우 수동 확인으로 남긴다.

```python
linear = channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
ratio = (max(luminance_a, luminance_b) + 0.05) / (min(luminance_a, luminance_b) + 0.05)
```

- [ ] audit.py 계약 테스트를 먼저 RED로 만든다. 잘못된 상태·여분 필드·빠진 주제·근거 없는 판정·결론/개별 check 불일치를 거절한다. 모델 입력에 fixture mode나 TTS 원문이 없음을 확인한다.
- [ ] schema를 엄격히 검증하고 반환 verdict를 check 상태와 대조한다. missing/contradicted 하나라도 있으면 fail, 없고 uncertain이 있으면 needs_review, 모두 delivered면 pass다. 모델 API 호출은 이 모듈에만 둔다.
- [ ] 테스트 GREEN 후 작성한 코드만 단순화 검토. 변경하면 해당 검사 재실행. 검증한 Task 1 커밋.

## Task 2: 샘플과 실제 Daytona 실행

- [ ] 데모 샘플은 결제 버튼→처리 중→실패와 재시도 안내로 동작한다. 처리 중 음성은 재생되며 첫 상태는 최종 안내 없음. 수정 시 최종 안내 WAV를 실제 재생한다. 이미지 1개는 설명 검사용이다.
- [ ] worker의 검사 선택을 먼저 검증한다. rules만 선택한 실행에서 judge·TTS·ASR 대역 호출은 0회여야 한다. AI 오류가 나도 rules 결과가 남아야 한다. 이는 분기 검증이며 실제 클라우드 성공의 증거로 쓰지 않는다.
- [ ] runner는 mcr.microsoft.com/playwright/python:v1.63.0-noble 이미지의 비공개 임시 샌드박스를 생성하고 필요한 모듈과 샘플을 업로드한다. PulseAudio·FFmpeg·한글 폰트 설치. auto-stop/TTL과 close 정리를 설정한다.
- [ ] worker는 로컬 HTTP 서버로 샘플을 제공한다. 음성 검사 선택 시에만 필요한 샘플 TTS를 생성·보관한다. 실제 녹음 전에는 정답·소스 문장을 판정 함수에 전달하지 않는다.

```python
browser = playwright.chromium.launch(
    headless=True, ignore_default_args=['--mute-audio'],
    args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
# 녹음 입력: PulseAudio null sink의 a11y.monitor
# FFmpeg 출력: mono, 16000Hz, PCM WAV
```

- [ ] 버튼 전부터 녹음하고 최종 화면 뒤 8초까지 관찰한다. 무음·녹음 오류는 통과로 바꾸지 않는다. WAV 길이는 헤더 nframes만 믿지 않고 실제 PCM 바이트로 확인한다. 화면·텍스트·새 녹음의 전사로 음성을 판단한다.
- [ ] 선택된 이미지 검사는 최대 3개, 샘플은 1개다. 누락 자체가 확정된 이미지에 같은 유무 질문으로 AI를 중복 호출하지 않는다. 빈 alt나 비어 있지 않은 설명의 의미는 실제 이미지·주변 문맥으로 판정한다. 잘림/로딩 실패는 보류·오류로 표시한다.
- [ ] 실제 모델에서 음성 누락 fail/바꿔 쓴 정상 pass/불명확 needs_review, 이미지 잘못된 설명 fail/정상 설명 pass를 확인한다. 실험 결과와 호출 지연을 저장한다.
- [ ] 실제 Daytona 1건으로 화면·녹음·전사·규칙 결과·의미 판정을 확보한다. 실패 시 근거를 보존하고 원인만 수정한다. GREEN 단순화 검토 후 Task 2 커밋.

## Task 3: API·단일 화면·실제 전후 시연

- [ ] app.create_app(runner, runtime)으로 API를 만들기 전 단일 작업 제어 테스트 RED. 두 번째 실행과 진행 중 fix/reset/close는 409, 실제 작업 오류는 error, 경로 탈출은 404, 두 실행 ID와 파일은 독립이어야 한다.
- [ ] GET /api/state, POST /api/prepare·run·fix·reset·close, GET /artifacts/{run_id}/{filename}. run의 checks는 rules/audio/alt_text 중 비어 있지 않은 목록만 허용한다.

```python
with lock:
    if state['busy']:
        raise HTTPException(409, '검사가 진행 중입니다.')
    state['busy'] = True
    run_id = uuid.uuid4().hex
    sample_snapshot = dict(sample)
# 단일 ThreadPoolExecutor 작업의 finally에서 busy를 해제한다.
```

- [ ] fix는 현재 revision의 완료된 음성 실패 후에만 최종 안내 설정을 바꾼다. AI 결과를 수정하지 않는다. reset은 샘플을 초기 상태로, close는 소유한 샌드박스를 삭제한다.
- [ ] frontend-design을 적용해 단일 한국어 화면을 만든다. 검사 선택, 실행·수정·재검사, 실제 상태, 규칙 결과, 화면·녹음·전사·이미지 판정, 전후 비교. 모델/페이지 텍스트는 textContent로 출력한다. 오디오 자동 재생 없음. 실제 진행 단계만 표시한다.
- [ ] 127.0.0.1:8090에서 실행한다. 데스크톱 브라우저에서 실제 prepare→run→음성 재생→fix→run→전후 비교→close를 확인한다. 핵심 버튼·키보드 포커스·증거 가독성을 점검한다.
- [ ] 전체 unittest GREEN, 단순화 검토, 실제 결과의 새 ID·파일 해시·정리 결과 확인 후 1명의 독립 리뷰를 요청한다. 리뷰 중 발표 결과 페이지와 실행 안내를 준비한다. 구체적 결함을 수정하고 영향받은 검사만 재실행한다.
- [ ] README에 설치·키 이름·실행·초기화·증거 경로·실제 검증 횟수·범위 한계를 기록한다. 최종 PDF 결과 장은 실제 증거만 사용한다. Task 3 커밋.

## Final Verification

- [ ] unittest 실행 결과 통과.
- [ ] 규칙 검사 5개가 모델 없이 동작하고 정상/결함 사례를 구분.
- [ ] 실제 음성 누락→설정 수정→새 녹음 통과, 이미지 의미 판정 정상/결함 확인.
- [ ] AI 오류와 규칙 결과 분리, 중복 실행·경로 접근 방어 확인.
- [ ] 브라우저에서 제품 전체 흐름과 실제 진행 상태 확인.
- [ ] 독립 리뷰 완료, 구체적 결함 해결, 실제 샌드박스 정리 확인.
- [ ] 완료 보고에는 측정한 것과 미검증 한계를 구분. 1시간이 지나 미완료면 남은 기능을 숨기지 않는다.

## Plan Self-Review

현재 5개 규칙과 두 AI 작업은 Task 1–2, 실행 격리·수정·UI는 Task 3에 대응한다. 기존 음성 시연을 유지하며 외부 검사 엔진은 없다. Review Focus 5개에 대응하는 확인이 있다. 작업별 인터페이스와 결과 종류를 일치시켰다. 이 문서가 유일한 구현 체크리스트다. 변경된 구현 계획의 사용자 확인 후 실행한다.

## 과거 중단 기록 (Git 협업 준비 요청으로 해제)

현재는 설계·계획 정리가 완료된 중단 지점이다. 사용자 요청에 따라 추가 작업을 멈춘다.

- 현재 범위: 자체 기본 검사 5개(이미지 대안, 단색 대비, 폼 레이블, 버튼 이름, 글자 크기 주의) + AI 음성·이미지 의미 검사.
- 현재 구현 계획은 이 문서이며 사용자 검토 전이다. 제품 코드와 accessibility-qa 폴더는 아직 만들지 않았다.
- 진행 중인 구현·모델 호출·Daytona 작업은 없다. 앞선 사전 실험의 샌드박스는 삭제됐다.
- 사전 발표 PDF 2장은 output/pdf/accessibility-qa-prelaunch.pdf에 있다. 실제 제품 결과는 아직 없다.
- 재개 시 이 중단 기록과 최신 사용자 조건을 먼저 확인하고, 해커톤 남은 시간에 맞춰 실행 시간을 다시 확인한다. 이전 시간표만 보고 자동으로 착수하지 않는다.


## Git 협업 실행 계약

2026-09-19 사용자 요청으로 Git 병렬 협업으로 변경한다. 확정 원격: https://github.com/minchael03/daytona.git (최초 조회 시 빈 저장소). 이 절이 앞부분의 단독 구현 방식, 로컬 저장소 초기화, 14:23 기준 시간표, 파일 위치를 대체한다. 기능 요구와 테스트 체크리스트는 유지한다. 제품 파일은 저장소 루트에 둔다. 이 문서가 유일한 구현 계획이다.

현재는 협업 준비 단계이며 제품 코드는 없다. 계획 검토 후 구현한다. 외부 에이전트에게 자동 메시지를 발송하지 않으며 사용자가 아래 지시문을 전달할 수 있다. 내부 보조 에이전트는 파일 경계와 계약의 읽기 전용 검토만 수행했다.

### 담당과 순서

| 시간 예산 (구현 착수 후) | 리드: lead/integration | 외부 담당: agent/rules-ui |
|---|---|---|
| 첫 25분 | 환경·샘플·실제 Daytona 녹음·ASR | 규칙 테스트 → 구현 → 첫 커밋 push |
| 다음 15분 | AI 판정·API·잠금·오류 처리, 규칙 통합 | 예제 JSON으로 UI → 두 번째 커밋 push |
| 이후 | 실제 전후 실행·전체 검증·독립 리뷰 | 실제 API와 연결된 UI 수정 |

완료 시간 보장은 아니다. 착수 때 실제 마감과 남은 시간을 확인한다. 선택 스폰서·장식이 실제 음성 전후 흐름을 늦추지 않게 한다. AI 이미지 검사는 유지하고 실제 완료 여부를 별도로 확인한다.

파일 소유권은 AGENTS.md를 따른다. 규칙과 UI를 한 커밋까지 기다리지 말고 규칙부터 전달한다. 샘플은 음성 흐름과 결합되므로 리드가 소유한다. 문서·requirements·공통 계약도 리드만 수정한다.

### 계약 1: 규칙 모듈

- Playwright **동기 API**. `rules.scan(page) -> {"snapshot": dict, "findings": list}`. 호출자가 page를 열고 닫는다.
- `inspect_snapshot(snapshot: dict) -> list[dict]`: 순수 함수. snapshot 내부 구조는 규칙 담당 소유이며 worker/UI는 해석하지 않는다.
- `contrast_ratio(rgb_a, rgb_b) -> float`: RGB는 0..255의 세 채널.
- `required_contrast(font_size: float, weight: int) -> float`, `meets_contrast(ratio: float, threshold: float) -> bool`.
- 파일 쓰기·HTTP·모델 API 호출 없음. DOM을 수정하지 않고 JSON 직렬화 가능한 결과를 반환한다.

```json
{"rule_id":"font_size","status":"needs_review","target":"#help","summary":"글자가 제품 권장값보다 작습니다.","evidence":{"font_size_px":12,"recommended_min_px":16},"basis":"product-guidance"}
```

- rule_id: `image_alt | contrast | form_label | button_name | font_size`.
- status: `pass | fail | needs_review | info`.
- basis: 대비 `wcag-1.4.3`, 크기 `product-guidance`, 나머지 `basic-presence`.
- target: 현재 페이지의 실제 요소를 다시 찾을 CSS 선택자. evidence: JSON 객체.
- 크기 16px 미만은 needs_review, 이상은 info 또는 생략. 크기만으로 접근성 pass를 만들지 않는다.
- 이름 유무 pass는 의미 적합성 pass가 아니다. 빈 alt·복잡한 대비는 needs_review.
- worker가 보이는 img와 의미 검사 후보를 직접 수집한다. 확정 image_alt/fail 대상은 반환된 선택자로 요소를 찾아 중복 AI 검사에서 제외한다. rules는 DOM에 ID·속성을 삽입하지 않는다.

### 계약 2: HTTP

같은 origin의 FastAPI + 정적 HTML/CSS/JS. UI는 약 1초 간격으로 state를 조회하며 poll을 중첩하지 않는다. 가짜 진행률 대신 stage를 표시한다.

| 요청 | 본문 | 성공 |
|---|---|---|
| GET /api/state | 없음 | 200 상태 JSON |
| POST /api/prepare | 없음 | 202 `{"accepted":true}`; 완료 후 prepared=true |
| POST /api/run | `{"checks":["rules","audio","alt_text"]}` | 202 `{"run_id":"새 ID"}` |
| POST /api/fix | 없음 | 200 `{"revision":1}`; 실제 음성 설정 수정 |
| POST /api/reset | 없음 | 200 `{"revision":2}`; 새 revision의 원래 결함 상태 |
| POST /api/close | 없음 | 202 `{"accepted":true}`; 삭제 완료 후 prepared=false |
| GET /artifacts/{run_id}/{filename} | 없음 | 200 파일 또는 404 |

checks는 위 세 문자열의 비어 있지 않은 중복 없는 배열. 잘못된 입력 422, busy 동안 변경 요청 409. 준비 전 run, 허용되지 않은 fix도 409. 오류 본문은 `{"detail":...}`. detail은 문자열 또는 FastAPI 검증 오류 배열일 수 있다. UI는 둘 다 텍스트로 안전하게 표시한다. prepare/close도 busy를 사용하고 비동기 오류는 state.error에 남긴다. reset/close는 이전 증거를 지우지 않는다.

can_fix는 서버에서 결정: busy=false, 현재 revision의 완료된 실행에서 audio verdict=fail, 아직 최종 음성 안내가 수정되지 않은 상태. UI는 재판정하지 않는다. 재검사는 /api/run의 새 호출이다.

### 계약 3: 상태·결과 예시

아래는 **개발용 fixture 예시**이며 실제 실행 증거가 아니다. UI fixture로 복사해 사용할 수 있다.

```json
{
  "busy": false,
  "prepared": true,
  "stage": "검사 완료",
  "error": null,
  "revision": 0,
  "can_fix": true,
  "current_run_id": "fixture-001",
  "runs": [{
    "run_id": "fixture-001",
    "revision": 0,
    "status": "complete",
    "elapsed_ms": 18000,
    "error": null,
    "artifacts": {
      "screen": "/artifacts/fixture-001/screen.png",
      "recording": "/artifacts/fixture-001/recorded.wav",
      "result": "/artifacts/fixture-001/result.json"
    },
    "rules": {"status":"complete","error":null,"elapsed_ms":50,"findings":[]},
    "audio": {
      "status": "complete",
      "error": null,
      "elapsed_ms": 15000,
      "transcript": "결제를 처리 중입니다.",
      "verdict": "fail",
      "summary": "실패 결과와 재시도 안내가 음성에 없습니다.",
      "provider": "openai",
      "model": "gpt-4.1-mini",
      "checks": [
        {"topic":"payment_result","status":"missing","visual_evidence":"결제에 실패했습니다.","provided_evidence":"결제를 처리 중입니다.","reason":"최종 결과가 없습니다."},
        {"topic":"next_action","status":"missing","visual_evidence":"다시 시도 버튼을 눌러 주세요.","provided_evidence":"결제를 처리 중입니다.","reason":"다음 행동 안내가 없습니다."}
      ]
    },
    "alt_text": {"status":"not_run","error":null,"elapsed_ms":null,"items":[]}
  }]
}
```

- 초기 state: busy=false, prepared=false, stage="대기", error=null, revision=0, can_fix=false, current_run_id=null, runs=[].
- runs는 최신순. 시작 즉시 새 실행을 추가하고 status=running, elapsed_ms=null.
- run.status: `running | complete | partial | error`. 접근성 fail은 실행 오류가 아니므로 complete 가능. 일부 검사 오류와 다른 완료가 공존하면 partial, 전부 오류 또는 실행 기반 오류면 error.
- 섹션 status: `not_run | running | complete | error`. 미선택 섹션도 유지한다.
- verdict: `pass | fail | needs_review`, 미실행/오류는 null. 오류를 접근성 fail이나 pass로 바꾸지 않는다.
- audio 미실행 기본: status=not_run, error/elapsed_ms/transcript/verdict/summary/provider/model=null, checks=[]. rules 기본: status=not_run, error/elapsed_ms=null, findings=[].
- artifacts는 screen/recording/result 키를 항상 포함하고 아직 없으면 null. UI는 서버 URL을 사용하고 직접 조립하지 않는다. 오류 시에도 수집된 증거는 남긴다.
- provider/model은 실제 의미 판정 공급자/모델. elapsed_ms는 섹션 전체 시간이며 모델 단독 지연으로 표시하지 않는다.
- alt_text.items 각 항목: target, image_url, supplied_text, status, error, verdict, summary, provider, model, elapsed_ms, checks. status=`complete | error | not_run`; null 규칙은 audio와 같다. checks topic은 image_description. image_url은 실제 캡처 URL 또는 null.
- 최대 3개 초과 또는 규칙 확정 누락으로 생략한 이미지도 status=not_run, verdict=null, summary에 이유를 남긴다.
- 추가 필드는 UI가 무시한다. 기존 필드 이름·타입·의미 변경은 리드가 문서와 담당자 합의를 먼저 갱신한다.

### 외부 에이전트 작업 지시 (그대로 전달 가능)

> https://github.com/minchael03/daytona 를 독립 clone하고 AGENTS.md, 설계, 구현 계획의 Git 협업 실행 계약을 읽어라. 리드 에이전트와 병렬 작업한다. 담당은 rules.py, tests/test_rules.py, tests/fixtures/rules/**, static/index.html, static/style.css, static/app.js, tests/fixtures/ui/**뿐이다. main에서 agent/rules-ui 브랜치를 만들고 자기 브랜치만 커밋·push한다. API·Daytona·AI·sample·의존성·공통 문서는 리드 소유이며 수정하지 마라.
>
> 1. 규칙부터 구현하라. 동기 Playwright scan, 순수 inspect_snapshot, 대비 함수들을 계약대로 구현한다. 이미지 대안·단색 대비·폼 레이블·버튼 이름·작은 글씨 주의만 만든다. 외부 접근성 엔진·모델 API 금지. 실제 Chromium HTML fixture로 ARIA 이름, label, 이미지 alt 버튼, 빈 버튼, placeholder-only, 빈 alt, gradient, 작은 글씨를 검사하라. 대비 21:1·1:1·4.499 경계·큰 글씨 3:1도 검증하라. 의미 있는 실패 테스트 → 최소 구현 → GREEN 단순화 검토를 수행하라. 명령: python -m unittest discover -s tests -p test_rules.py -v. 런타임 문제로 실행 못한 검사는 미검증으로 보고하라.
>
> 2. 규칙 완료 즉시 담당 파일만 커밋하고 git push -u origin agent/rules-ui. 브랜치/커밋 SHA/변경 파일/실행 검사와 결과/미검증 사항/계약 변경 요청 형식으로 리드에게 전달하라. UI 완료까지 기다리지 마라.
>
> 3. 단일 한국어 UI를 구현하라. 기본 세 검사 선택, 환경 준비, 검사 실행, 음성 안내 수정, 재검사, 초기화, 환경 종료. API 계약 준수. fixture는 tests/fixtures/ui 안에서만 사용하고 제품에 가짜 결과 fallback을 넣지 마라. 규칙/음성/이미지 결과를 분리하고 실제 화면, 오디오 controls, 전사, 공급자/모델, 섹션 처리 시간, 실행 ID와 수정 전후 결과를 표시하라. 실패/오류/확인 필요/미실행을 구별하고 busy/prepared/can_fix로 버튼을 제어하라. 409/422와 네트워크 오류를 표시하고 모든 외부 문자열은 textContent로 출력하라. 오디오 자동 재생 금지. 키보드 포커스와 대비 확보. 추가 프레임워크·패키지·통계 화면 금지.
>
> 4. 초기/실행 중/누락 fail/수정 후 pass/AI 오류+규칙 완료/needs_review 상태를 fixture로 확인하라. 실제 API 연결은 리드와 함께 확인한다. 두 번째 커밋을 push하고 같은 인계 형식으로 보고하라. 계약 변경은 먼저 리드에게 제안하고 독립 작업을 계속하라.

### 리드 통합 체크리스트

- [ ] 계획 검토 뒤 lead/integration에서 기존 Task 1–3의 리드 소유 항목 구현.
- [ ] 외부 규칙 커밋의 diff·스펙·코드 품질 검토, 규칙 테스트 실행, JSON 직렬화·DOM 비변경 확인 후 정확한 SHA 병합.
- [ ] rules만 실행하면 TTS/ASR/LLM 0회, AI 실패에도 규칙 보존 확인.
- [ ] UI diff·API 계약·문자열 출력·가짜 결과 부재 확인 후 정확한 SHA 병합.
- [ ] 전체 unittest, 실제 Daytona 누락→수정→새 녹음 pass, 이미지 정상/결함, 새 ID·파일, 동시 요청 409, 증거 경로 제약 확인.
- [ ] 독립 최종 리뷰·브라우저 시연 후 결함 수정. README에 실제 완료 범위와 한계 기록.
- [ ] main 최신 변경 fetch 후 확인, 충돌 해결·통합 검증 후 main 병합·push. 타인 작업 덮어쓰기 금지.

### Git 명령 예시

외부 담당의 독립 clone:

```sh
git clone https://github.com/minchael03/daytona.git
cd daytona
git switch -c agent/rules-ui origin/main
# 구현·검증 후 실제 담당 파일만 add
git add rules.py tests/test_rules.py
git diff --cached --check
git commit -m "feat: implement five native accessibility checks"
git push -u origin agent/rules-ui
```

브랜치가 이미 존재하면 덮어쓰지 말고 fetch 후 기존 자기 브랜치를 사용한다. 리드는 전달받은 SHA가 원격 담당 브랜치의 조상인지 확인한 뒤 `git merge --no-ff <SHA>`로 병합한다. 진행 중 브랜치의 미검토 최신 커밋을 통째로 병합하거나 cherry-pick과 merge로 중복 반영하지 않는다.

### 협업 계획 검토

독립 읽기 전용 검토의 제안(파일 소유권, sync Playwright, JSON 상태, can_fix, 오류 응답)을 반영했다. snapshot 내부 구현을 공유 계약에서 제외해 불필요한 결합을 줄였다. 기존 5가지 규칙과 2가지 AI 작업 범위 유지 여부를 자체 검토했다. 제품 구현·통합 테스트는 아직 없다.

## 실행 기록 (리드)

- 사용자 분업 승인 후 lead/integration에서 착수. 전용 독립 clone을 사용하며 새 worktree는 만들지 않는다.
- Ruling: 진행 기록은 사용자 지시대로 이 계획에 유지한다. 별도 중복 ledger/checklist를 만들지 않는다.
- Pre-flight: rules.scan(sync page) → worker; runner.run → app; app JSON → UI 계약 확인. 외부 담당 파일은 수정하지 않는다.
- API·AI 판정 계약: 모듈 없음으로 RED 확인 후 구현, unittest 6개 GREEN. 작성 코드 단순화 검토: 별도 서비스 계층 없이 단일 잠금·함수 유지.
- Ruling: ASR·AI·TTS는 로컬 runner에서 호출하고 Daytona worker는 브라우저 실행·녹음·DOM 증거를 담당한다. API 키를 원격에 복사하지 않고도 실제 Daytona 출력 검증이 가능하며 사용자 흐름·공개 API 계약은 동일하다.
- OpenAI 음성/전사/Chat Completions 공식 API 문서 확인. Nosana는 선택 통합으로 핵심 실제 실행 검증 이후 다룬다.
- 리드 테스트 10개 GREEN: API 3, AI 계약 3, 녹음/분기 3, 실제 로컬 Chromium 샘플·이미지 증거 1. 기존 Starlette의 httpx deprecation 경고는 동작 실패와 구분한다.
- GREEN 단순화 검토: 모델 호출은 audit에, 오디오 공급자 호출은 runner에 한정. worker는 비밀키 없는 증거 수집 전용. 불필요한 프레임워크를 추가하지 않았다.
- 실제 Daytona 전후 리허설 실행 중. 이 커밋은 외부 rules/UI 통합 전 리드 구현이며 전체 MVP 완료를 의미하지 않는다.
