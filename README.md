# 네트워크 장비 점검 및 백업 자동화 도구

엑셀로 관리하는 장비 목록을 읽어 SSH/Telnet으로 접속하고, 점검 결과와 설정 백업을 자동으로 생성하는 Python 도구입니다.

## 핵심 기능

- 벤더 모듈 자동 로딩 및 확장 (`vendors/`에 모듈 추가)
- 점검/백업 모드 선택 실행 (점검만, 백업만, 둘 다)
- 엑셀 기반 장비 관리, 암호화된 엑셀 파일 지원
- 사용자 명령 파일 실행 (TXT/엑셀 명령 목록)
- SSH/Telnet 지원, 장비별 커스텀 핸들러 등록
- 병렬 처리(최대 10대), 진행률 표시 및 세션 로그 분리
- TCP 연결 사전 테스트 및 재시도/백오프
- 결과 엑셀 리포트 생성 및 실패 항목 하이라이트
- 콘솔 로그 레벨 및 점검 제외 항목 설정
- 입력 데이터 유효성 검증 (IP/포트/벤더/OS/중복)

## 지원 장비

| 벤더 (Vendor) | 운영체제 (OS) |
| :--- | :--- |
| `alcatel-lucent` | `aos6`, `aos8` |
| `axgate` | `axgate` |
| `cisco` | `ios`, `ios-xe`, `legacy` |
| `dayou` | `dsw` |
| `handreamnet` | `hn` |
| `juniper` | `junos` |
| `nexg` | `vforce` |
| `piolink` | `tifront` |
| `ruckus` | `icx` |
| `ubiquoss` | `e4020` |

## 빠른 시작

### 요구사항
- Windows 환경 (CLI 메뉴 입력에 `msvcrt` 사용)
- Python 3.8+
- Tkinter 미설치 시 파일/암호 입력은 콘솔로 대체됩니다.

### 설치
```bash
pip install -r requirements.txt
```

## 엑셀 입력 형식

필수 컬럼:
- `ip`, `vendor`, `os`, `connection_type`, `port`, `password`

선택 컬럼:
- `username`, `enable_password`

예시:

| ip | vendor | os | connection_type | port | username | password | enable_password |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 192.168.1.1 | cisco | ios | ssh | 22 | admin | cisco123 | class |
| 10.0.0.5 | ruckus | icx | ssh | 22 | super | sp-pass | |

지원 확장자:
- 장비 목록: `.xlsx`, `.xls`, `.xlsm`
- 암호화된 엑셀은 `msoffcrypto-tool` 필요

유효성 검증:
- IP 형식, 포트 범위(1-65535), `ssh/telnet`만 허용
- 벤더/OS 지원 조합 검증 및 IP 중복 검사
- 컬럼명은 대소문자 구분 없이 인식

## 사용 방법

1) 실행
```bash
python main.py
```

2) 메뉴 선택  
화살표/Enter로 메뉴를 선택합니다.

3) 엑셀 파일 경로 입력  
탭 자동완성을 지원하며, 암호화된 파일은 암호 입력을 요청합니다.

4) (점검 포함 시) 결과 열 순서 설정  
작업 실행 전에 열 순서를 정할지 묻습니다.  
`y`를 선택하면 점검 항목 목록에서 Enter로 이동 모드를 전환하여 순서를 변경합니다.

## 사용자 명령 파일 실행

메인 메뉴에서 "사용자 명령 파일 실행"을 선택하면 장비에 임의 명령을 일괄 실행할 수 있습니다.

- 텍스트 파일: 한 줄에 한 명령
- 엑셀 파일: 첫 번째 컬럼에 명령을 한 줄씩 입력
- 공백/빈 행은 무시됩니다.
- 여러 벤더/OS가 섞인 경우 경고가 표시됩니다.

## 결과물

- 점검 결과: `results/inspection_results_YYYYMMDD_HHMMSS.xlsx`
- 명령 실행 결과: `results/command_results_YYYYMMDD_HHMMSS.xlsx`
- 설정 백업: `backup/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].txt`
- 실행 로그: `logs/network_inspector_YYYYMMDD_HHMMSS.log`
- 세션 로그: `session_logs/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].log`

세션 로그에는 연결/명령 실행 결과가 포함되며, 점검/백업 여부와 관계없이 생성됩니다.

## 연결 및 타임아웃 기본값

- 연결 타임아웃: 10초, 최대 재시도: 3회 (지수 백오프)
- TCP 연결 사전 테스트: 5초
- 명령 읽기 타임아웃: 점검 30초, 백업 60초
- 병렬 처리: 장비 최대 10대, 점검+백업 시 작업이 병렬로 실행됩니다.

## 설정 (settings.json)

파일이 없으면 프로젝트 루트에 자동 생성됩니다.

- `console_log_level`: `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`
- `inspection_excludes`: 벤더/OS/파싱 항목 단위 제외 설정  
  - 값은 `명령어` 또는 `명령어::컬럼명` 형태로 저장됩니다.
  - 설정 메뉴에서 단계별 모두 포함/제외 지원 (전체/벤더/OS), 변경 시 `y/N` 확인
- 배너 문구는 `main.py`의 `BANNER` 리스트에서 변경합니다.

## 프로젝트 구조

```
network-device-inspection-1/
├── main.py
├── requirements.txt
├── core/
│   ├── inspector.py
│   ├── file_handler.py
│   ├── validator.py
│   ├── settings.py
│   ├── logging_config.py
│   └── ui.py
├── vendors/
│   ├── __init__.py
│   ├── base.py
│   └── [vendor].py
├── results/          # 자동 생성
├── backup/           # 자동 생성
├── logs/             # 자동 생성
└── session_logs/     # 자동 생성
```

## 신규 벤더 추가

1) `vendors/[벤더명].py` 생성  
2) 아래 딕셔너리 정의  
   - `[벤더명]_INSPECTION_COMMANDS`
   - `[벤더명]_BACKUP_COMMANDS`
   - `[벤더명]_PARSING_RULES`
3) 필요 시 커스텀 파서 함수 추가 (`parsing_[벤더]_[기능]`)
4) 로그인/특수 처리 필요 시 `CustomDeviceHandler` 상속 후 `@register_handler` 등록

## 로깅

- 파일 로그는 항상 DEBUG 레벨로 저장됩니다.
- 콘솔 로그 레벨은 `settings.json`의 `console_log_level`로 조정합니다.
- 기본 로그 포맷: `%(asctime)s | [%(threadName)s] | %(levelname)s | %(message)s`

## EXE 빌드 (PyInstaller)

```powershell
pyinstaller --onefile --name "NetworkInspector" `
  --hidden-import "vendors.alcatel_lucent" `
  --hidden-import "vendors.axgate" `
  --hidden-import "vendors.cisco" `
  --hidden-import "vendors.dayou" `
  --hidden-import "vendors.handreamnet" `
  --hidden-import "vendors.juniper" `
  --hidden-import "vendors.nexg" `
  --hidden-import "vendors.piolink" `
  --hidden-import "vendors.ruckus" `
  --hidden-import "vendors.ubiquoss" `
  main.py
```

## 라이선스

MIT License. 자세한 내용은 `LICENSE` 참고.