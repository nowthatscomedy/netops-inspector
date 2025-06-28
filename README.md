# 네트워크 장비 점검 및 백업 자동화 도구

이 프로젝트는 다양한 네트워크 장비의 상태를 점검하고 설정을 백업하는 작업을 자동화하는 Python 스크립트입니다. 엑셀 파일에 장비 목록을 정리해두면, 스크립트가 SSH 또는 Telnet으로 각 장비에 접속하여 필요한 정보를 수집하고 결과를 깔끔한 엑셀 파일로 정리해줍니다.

## ✨ 주요 기능

- **다양한 벤더 지원**: Cisco, Juniper 등 여러 네트워크 장비 벤더를 지원합니다.
- **엑셀 기반 관리**: 점검할 장비 목록을 `devices.xlsx` 파일 하나로 관리합니다.
- **유연한 연결 방식**: SSH 및 Telnet 프로토콜을 모두 지원합니다.
- **병렬 처리**: 다수의 장비를 동시에 점검하여 작업 시간을 단축합니다.
- **자동 결과 리포트**: 점검 결과를 타임스탬프가 포함된 `inspection_results_...xlsx` 파일로 자동 생성합니다.
- **상세 로그**: 모든 작업 과정과 장비와의 통신 내용을 로그 파일로 기록하여 문제 발생 시 원인 파악이 용이합니다.
- **선택적 실행 모드**: '점검만', '백업만', 또는 '점검과 백업 모두' 실행할 수 있습니다.
- **안정적인 실행**: 연결 실패 시 자동으로 재시도하는 등 오류 처리 로직이 포함되어 있습니다.

## 🔧 지원 장비

| 벤더 (Vendor) | 운영체제 (OS) |
| :--- | :--- |
| `cisco` | `ios`, `ios-xe`, `legacy` |
| `juniper` | `junos` |
| `alcatel-lucent` | `aos6`, `aos8` |
| `axgate` | `axgate` |
| `nexg` | `vforce` |
| `ubiquoss` | `e4020` |
| `piolink` | `tifront` |

> **참고**: `devices.xlsx` 파일 작성 시 위 테이블의 `벤더`와 `운영체제` 값을 정확히 사용해야 합니다.

## 📁 디렉토리 구조

```
.
├── network-device-inspection.py  # 메인 스크립트
├── requirements.txt              # 파이썬 의존성 파일
├── devices.xlsx                  # [사용자 생성] 장비 정보 입력 파일
├── vendors/                      # 벤더별 설정 모듈
│   ├── __init__.py
│   ├── base.py
│   ├── cisco.py
│   └── ... (기타 벤더 파일)
│
├── backup/                       # (자동 생성) 설정 백업 디렉토리
│   └── 20230101_120000/
│       └── 192.168.1.1_cisco_ios.txt
├── logs/                         # (자동 생성) 프로그램 실행 로그 디렉토리
│   └── network_inspector_20230101_120000.log
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
| 192.168.1.2 | juniper | junos | ssh | 22 | user | juniper! | |
| 192.168.1.3 | cisco | legacy | telnet | 23 | | cisco | enable_pass |
| 10.0.0.1 | ubiquoss | e4020 | telnet | 23 | ubi | ubi123 | |

### 2단계: 스크립트 실행

터미널에서 아래 명령어를 실행합니다.

```bash
python network-device-inspection.py
```

실행 후, 원하는 작업 모드를 선택합니다.

```
=== 네트워크 장비 점검 및 백업 도구 ===
1. 점검만 실행
2. 백업만 실행
3. 점검과 백업 모두 실행

실행할 작업을 선택하세요 (1-3):
```

### 3단계: 결과 확인

작업이 완료되면 아래와 같은 결과물들이 생성됩니다.

- **점검 결과**: `inspection_results_YYYYMMDD_HHMMSS.xlsx`
  - 장비별 점검 항목과 결과가 정리된 엑셀 파일입니다. 접속 실패 등 문제가 있는 항목은 빨간색으로 표시됩니다.
- **설정 백업**: `backup/YYYYMMDD_HHMMSS/`
  - 장비들의 `running-config` 등 설정 정보가 텍스트 파일로 백업됩니다.
- **로그**: `logs/` 및 `session_logs/`
  - 스크립트 실행 로그와 각 장비와의 자세한 통신 로그가 기록되어, 문제 해결에 도움을 줍니다.


## 👨‍💻 개발자를 위하여: 신규 장비 추가하기

이 도구는 새로운 벤더나 장비 모델을 쉽게 추가할 수 있도록 모듈화된 구조로 설계되었습니다.

1.  **벤더 모듈 생성**:
    - `vendors/` 디렉토리에 `[벤더명].py` 파일을 생성합니다. (예: `vendors/new_vendor.py`)

2.  **명령어 및 파싱 규칙 정의**:
    - 생성한 파일 안에 아래와 같은 딕셔너리들을 정의합니다.
      - `[벤더명]_INSPECTION_COMMANDS`: 점검에 필요한 명령어 목록
      - `[벤더명]_BACKUP_COMMANDS`: 백업에 사용할 명령어
      - `[벤더명]_PARSING_RULES`: 각 명령어의 출력 결과를 파싱하기 위한 정규표현식 또는 커스텀 파싱 함수 규칙

3.  **커스텀 핸들러 구현 (필요 시)**:
    - 기본 `netmiko` 로 처리가 어려운 특별한 로그인 절차나 명령어 실행 방식이 필요하다면, `vendors/base.py` 의 `CustomDeviceHandler`를 상속받아 새로운 핸들러 클래스를 구현할 수 있습니다.
    - 구현한 핸들러는 `vendors/base.py`의 `get_custom_handler` 함수에 등록해야 합니다.

4.  **패키지 초기화 파일 수정**:
    - `vendors/__init__.py` 파일에 새로 추가한 벤더의 설정(`..._COMMANDS`, `..._PARSING_RULES`)과 커스텀 파싱 함수들을 임포트하고 `__all__` 리스트에 추가합니다.

자세한 구현 방식은 `vendors/` 디렉토리 내의 다른 벤더 파일들을 참고하세요.

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 `LICENSE` 파일을 참고하세요. 