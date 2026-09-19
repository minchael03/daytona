# A11yChecker

화면에는 보이지만 음성에는 빠진 중요한 안내를 찾는 키오스크 웹앱 QA MVP.

현재는 **협업 준비 단계**이며 실행 가능한 제품 코드는 아직 없다.

- [협업 규칙과 담당 파일](AGENTS.md)
- [설계와 검사 범위](docs/superpowers/specs/2026-09-19-accessibility-audio-qa-design.md)
- [구현 계획·API 계약·외부 에이전트 작업 지시](docs/superpowers/plans/2026-09-19-accessibility-audio-qa.md#git-협업-실행-계약)

핵심: 자체 규칙 5개 + 선택적 AI 음성/이미지 의미 검사. Daytona에서 실제 브라우저 출력 음성을 수집하고, 안내 수정 뒤 새 실행으로 재검증한다. 외부 접근성 검사 엔진은 사용하지 않는다.

외부 에이전트는 `AGENTS.md`를 읽고 구현 계획의 작업 지시를 따른다. API 키는 저장소나 공유 메시지에 포함하지 않는다.
