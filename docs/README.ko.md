# NetOps Inspector (한국어)

언어: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector는 멀티 벤더 네트워크 장비 점검/백업을 위한 CLI 도구입니다.
엑셀 장비 목록을 읽어 SSH/Telnet으로 접속하고, 점검 명령 실행 결과를 파싱해 결과 엑셀을 생성합니다.

## 주요 기능

- 멀티 벤더 구조 (`vendors/`)
- 점검 / 백업 / 점검+백업 모드
- TXT/엑셀 기반 커스텀 명령 배치 실행
- 입력 엑셀 유효성 검사 (필수 컬럼/중복 IP/벤더-OS 호환)
- 재시도/타임아웃/동시 작업 수 설정
- 실시간 TUI 대시보드
- 장비별 세션 로그
- 사용자 규칙 확장 (`custom_rules.yaml`)
- 다국어 UI (`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`)

## 빠른 시작

```bash
pip install -r requirements.txt
python main.py
```

메인 메뉴:

1. 점검/백업 시작
2. 커스텀 명령 파일 실행
3. 설정 변경
4. Netmiko `device_type` 목록 보기
5. 종료

## i18n

지원 언어 코드:

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

로케일 파일:

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`

## 설정 파일 (`settings.yaml`) 예시

```yaml
language: ko
fallback_language: en
console_log_level: WARNING
max_retries: 3
timeout: 10
max_workers: 10
```
