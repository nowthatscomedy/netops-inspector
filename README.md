# 네트워크 장비 점검 및 백업 자동화 도구

이 프로젝트는 다양한 네트워크 장비의 상태를 점검하고 설정을 백업하는 작업을 자동화하는 Python 스크립트입니다. 엑셀 파일에 장비 목록을 정리해두면, 스크립트가 SSH 또는 Telnet으로 각 장비에 접속하여 필요한 정보를 수집하고 결과를 깔끔한 엑셀 파일로 정리해줍니다.

## ✨ 주요 기능

- **동적 벤더 확장**: `vendors` 폴더에 새로운 벤더 모듈을 추가하기만 하면 자동으로 인식되어, 코드 수정 없이도 손쉽게 지원 장비를 확장할 수 있습니다.
- **자동 핸들러 등록**: `@register_handler` 데코레이터를 사용하여 벤더, OS, 접속 방식에 맞는 커스텀 핸들러를 간편하게 등록하고 관리할 수 있습니다.
- **엑셀 기반 관리**: 점검할 장비 목록을 단일 엑셀 파일로 관리하며, 암호화된 파일도 지원합니다.
- **유연한 연결 방식**: SSH 및 Telnet 프로토콜을 모두 지원합니다.
- **병렬 처리**: 다수의 장비를 동시에 점검하여 작업 시간을 단축합니다.
- **자동 결과 리포트**: 점검 결과를 `results/inspection_results_...xlsx` 파일로 자동 생성하며, 접속 실패 항목은 하이라이트 처리됩니다.
- **CLI UX 강화**: ASCII 배너, 컬러 로그, 진행률 바 등으로 실행 상태를 가독성 있게 표시합니다.
- **상세 로그**: 모든 작업 과정과 장비와의 통신 내용을 세션별 로그 파일로 기록하여 문제 발생 시 원인 파악이 용이합니다.
- **설정 관리**: 콘솔 로그 레벨을 메뉴에서 변경하고 `settings.json`에 자동 저장합니다.
- **선택적 실행 모드**: '점검만', '백업만', 또는 '점검과 백업 모두' 실행할 수 있습니다.
- **안정적인 실행**: 연결 실패 시 자동으로 재시도하는 등 오류 처리 로직이 포함되어 있습니다.

## 🔧 지원 장비

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

> **참고**: `devices.xlsx` 파일 작성 시 위 테이블의 `벤더`와 `운영체제` 값을 정확히 사용해야 합니다.

## 📁 디렉토리 구조

```
.
├── main.py                       # 메인 스크립트 (프로그램 시작점)
├── requirements.txt              # 파이썬 의존성 파일
├── devices.xlsx                  # [사용자 생성] 장비 정보 입력 파일
├── settings.json                 # (자동 생성) 콘솔 로그 레벨 설정
│
├── core/                         # 핵심 로직 패키지
│   ├── inspector.py              # 장비 점검/백업 로직 및 다중 처리
│   ├── file_handler.py           # 파일(엑셀) 처리
│   ├── validator.py              # 데이터 유효성 검증
│   ├── ui.py                     # GUI(파일/암호 대화상자) 처리
│   └── custom_exceptions.py      # 사용자 정의 예외
│
├── vendors/                      # 벤더별 설정 모듈
│   ├── __init__.py               # 동적 모듈/파서 로더
│   ├── base.py                   # 핸들러 기본 클래스 및 자동 등록
│   ├── alcatel_lucent.py
│   ├── axgate.py
│   ├── cisco.py
│   ├── dayou.py
│   ├── handreamnet.py
│   ├── juniper.py
│   ├── nexg.py
│   ├── piolink.py
│   ├── ruckus.py
│   └── ubiquoss.py
│
├── backup/                       # (자동 생성) 설정 백업 디렉토리
│   └── 20230101_120000/
│       └── 192.168.1.1_cisco_ios.txt
│
├── results/                      # (자동 생성) 점검 결과 디렉토리
│   └── inspection_results_20230101_120000.xlsx
│
├── logs/                         # (자동 생성) 프로그램 실행 로그 디렉토리
│   └── network_inspector_...log
│
└── session_logs/                 # (자동 생성) 장비별 세션 로그 디렉토리
    └── 20230101_120000/
        └── 192.168.1.1_cisco_ios.log
```

## ⚙️ 준비 및 설치

### 요구사항
- Python 3.8 이상

### 설치 과정
1.  **프로젝트 복제**
    ```bash
    git clone https://github.com/your-username/network-device-inspection.git
    cd network-device-inspection
    ```

2.  **가상환경 생성 및 활성화 (권장)**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **필요한 패키지 설치**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 사용 방법

### 1단계: `devices.xlsx` 파일 준비

프로젝트의 루트 디렉토리에 `devices.xlsx` 파일을 생성하고, 점검할 장비 정보를 아래 형식에 맞게 입력합니다.

**필수 컬럼**:
- `ip`: 장비 IP 주소
- `vendor`: 장비 벤더 ( [지원 장비](#-지원-장비) 섹션 참고)
- `os`: 장비 운영체제 ( [지원 장비](#-지원-장비) 섹션 참고)
- `connection_type`: `ssh` 또는 `telnet`
- `port`: 접속 포트 번호
- `password`: 장비 로그인 비밀번호

**선택 컬럼**:
- `username`: 장비 로그인 사용자 이름
- `enable_password`: 특권 모드(enable) 진입 시 필요한 비밀번호. 미입력 시 `password` 값을 사용합니다.

**입력 예시:**
| ip | vendor | os | connection_type | port | username | password | enable_password |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 192.168.1.1 | cisco | ios | ssh | 22 | admin | cisco123 | class |
| 10.0.0.5 | ruckus | icx | ssh | 22 | super | sp-pass | |
| 172.16.0.1 | dayou | dsw | ssh | 22 | dayou | dayou123 | dayou_en |

### 2단계: 스크립트 실행

터미널에서 아래 명령어를 실행합니다.

```bash
python main.py
```

실행 후, 메인 메뉴에서 작업을 시작하거나 설정을 변경할 수 있습니다.

```
_   _      _                      _   _           _
| \ | | ___| |___      _____  _ __| \ | | ___   __| | ___ _ __
|  \| |/ _ \ __\ \ /\ / / _ \| '__|  \| |/ _ \ / _` |/ _ \ '__|
| |\  |  __/ |_ \ V  V / (_) | |  | |\  | (_) | (_| |  __/ |
|_| \_|\___|\__| \_/\_/ \___/|_|  |_| \_|\___/ \__,_|\___|_|
RUN ID   : 20240101_120000
LOG FILE : logs/network_inspector_20240101_120000.log
-----------------------------------------
1) 작업 시작 (점검/백업 선택)
2) 설정 변경 (로그 출력 레벨)
3) 종료
>> 실행할 작업을 선택하세요 (1-3):
```

작업 시작을 선택하면 점검/백업 모드를 고르고, 이후 CLI에서 엑셀 파일 경로를 입력합니다. 파일이 암호화된 경우, 암호 입력창이 나타납니다.

예시:
```
>> 엑셀 파일 경로를 입력하세요 (예: test.xlsx 또는 C:\Users\PC\Desktop\test.xlsx):
```

### 3단계: 결과 확인

작업이 완료되면 아래와 같은 결과물들이 생성됩니다.

- **점검 결과**: `results/inspection_results_YYYYMMDD_HHMMSS.xlsx`
  - 장비별 점검 항목과 결과가 정리된 엑셀 파일입니다. 접속 실패 등 문제가 있는 항목은 빨간색으로 표시됩니다.
- **설정 백업**: `backup/YYYYMMDD_HHMMSS/`
  - 장비들의 `running-config` 등 설정 정보가 텍스트 파일로 백업됩니다.
- **로그**: `logs/` 및 `session_logs/`
  - 스크립트 실행 로그와 각 장비와의 자세한 통신 로그가 기록되어, 문제 해결에 도움을 줍니다.

## ⚙️ 설정 파일

`settings.json`은 콘솔 로그 출력 수준을 저장합니다. 파일이 없으면 기본값으로 시작하며, 메뉴에서 변경 시 자동으로 생성/갱신됩니다.

- `console_log_level`: `WARNING`, `INFO`, `DEBUG` 중 하나

## 📦 실행 파일 (EXE) 생성

`PyInstaller`를 사용하여 이 프로그램을 단일 실행 파일로 만들 수 있습니다.

1.  **PyInstaller 설치**
    ```bash
    pip install pyinstaller
    ```

2.  **EXE 파일 빌드**
    이 프로젝트는 `vendors` 디렉토리의 모듈들을 동적으로 불러오므로, 빌드 시 `--hidden-import` 옵션을 사용하여 각 벤더 모듈을 직접 명시해주어야 합니다.
    ```powershell
    pyinstaller --onefile --name "NetworkInspector" --hidden-import "vendors.alcatel_lucent" --hidden-import "vendors.axgate" --hidden-import "vendors.cisco" --hidden-import "vendors.dayou" --hidden-import "vendors.handreamnet" --hidden-import "vendors.juniper" --hidden-import "vendors.nexg" --hidden-import "vendors.piolink" --hidden-import "vendors.ruckus" --hidden-import "vendors.ubiquoss" main.py
    ```

3.  **결과 확인**
    빌드가 완료되면 `dist` 폴더에 `NetworkInspector.exe` 파일이 생성됩니다.

## 👨‍💻 개발자를 위하여: 신규 장비 추가하기

이 도구는 **자동 등록(Auto-discovery)** 기능을 통해 새로운 벤더나 장비 모델을 매우 쉽게 추가할 수 있도록 설계되었습니다. `vendors` 디렉토리 외 다른 파일은 수정할 필요가 없습니다.

1.  **벤더 모듈 생성**:
    - `vendors/` 디렉토리에 `[벤더명].py` 파일을 생성합니다. (예: `vendors/new_vendor.py`)

2.  **명령어 및 파싱 규칙 정의**:
    - 생성한 파일 안에 `[벤더명]_INSPECTION_COMMANDS`, `[벤더명]_BACKUP_COMMANDS`, `[벤더명]_PARSING_RULES` 딕셔너리들을 정의합니다.
    - 필요하다면, `parsing_[벤더명]_[기능]` 형태의 커스텀 파싱 함수를 정의하고 `vendors/__init__.py`에 등록합니다.

3.  **커스텀 핸들러 구현 및 등록**:
    - 특별한 로그인 절차나 명령어 처리가 필요하다면 `CustomDeviceHandler`를 상속받아 새로운 핸들러 클래스를 구현합니다.
    - 클래스 위에 `@register_handler` 데코레이터를 추가하여 어떤 `벤더`, `OS`, `접속 방식`을 처리할지 명시해주기만 하면 자동으로 등록됩니다.

**핸들러 등록 예시 (`vendors/new_vendor.py`):**
```python
from vendors.base import CustomDeviceHandler, register_handler

# ... (명령어 및 파싱 규칙 정의) ...

@register_handler('new_vendor', 'new_os', 'ssh')
class NewVendorSSHHandler(CustomDeviceHandler):
    def connect(self):
        # ... 접속 로직 구현 ...
    
    def enable(self):
        # ... 특권 모드 진입 로직 구현 ...
        
    # ... 기타 메소드 구현 ...
```

자세한 구현 방식은 `vendors/` 디렉토리 내의 다른 벤더 파일들(`cisco.py`, `ruckus.py` 등)을 참고하세요.

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 `LICENSE` 파일을 참고하세요. 