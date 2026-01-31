# 네트워크 장비 점검 및 백업 자동화 도구

엑셀로 관리하는 장비 목록을 읽어 SSH/Telnet으로 접속하고, 점검 결과와 설정 백업을 자동으로 생성하는 Python 도구입니다.

## 핵심 기능

- 벤더 모듈 자동 로딩 및 확장 (`vendors/`에 모듈 추가)
- 점검/백업 모드 선택 실행 (점검만, 백업만, 둘 다)
- 엑셀 기반 장비 관리, 암호화된 엑셀 파일 지원
- SSH/Telnet 지원, 장비별 커스텀 핸들러 등록
- 병렬 처리(최대 10대), 진행률 표시 및 세션 로그 분리
- 결과 엑셀 리포트 생성 및 실패 항목 하이라이트
- 콘솔 로그 레벨 및 점검 제외 항목 설정

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

## 사용 방법

1) 실행
```bash
python main.py
```

2) 메뉴 선택  
화살표/Enter로 메뉴를 선택합니다.

3) 엑셀 파일 경로 입력  
탭 자동완성을 지원하며, 암호화된 파일은 암호 입력을 요청합니다.

## 결과물

- 점검 결과: `results/inspection_results_YYYYMMDD_HHMMSS.xlsx`
- 설정 백업: `backup/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].txt`
- 실행 로그: `logs/network_inspector_YYYYMMDD_HHMMSS.log`
- 세션 로그: `session_logs/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].log`

## 설정 (settings.json)

파일이 없으면 자동 생성됩니다.

- `console_log_level`: `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`
- `inspection_excludes`: 벤더/OS/파싱 항목 단위 제외 설정  
  - 값은 `명령어` 또는 `명령어::컬럼명` 형태로 저장됩니다.

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