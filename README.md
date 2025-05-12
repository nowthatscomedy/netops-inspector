# Network Device Inspection

네트워크 장비 점검 및 설정 백업을 자동화하는 프로그램입니다.

## 주요 기능

- 엑셀 파일(`devices.xlsx`)을 통한 장비 정보 입력
- SSH/Telnet을 통한 장비 접속 (연결 실패 시 최대 3번 재시도)
- 장비별 점검 명령어 실행 및 결과 수집
- 설정 파일 백업 및 세션 로그 저장
- 결과를 엑셀 파일(`inspection_results.xlsx`)로 저장

## 시스템 요구사항

- Python 3.8 이상
- Windows/Linux/MacOS

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/your-username/network-device-inspection.git
cd network-device-inspection
```

2. 가상환경 생성 및 활성화
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/MacOS
python3 -m venv venv
source venv/bin/activate
```

3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

## 사용 방법

1. `devices.xlsx` 파일에 장비 정보 입력
   - 필수 컬럼: ip, vendor, model, connection_type, port, username, password
   - connection_type: ssh 또는 telnet
   - port: SSH(22) 또는 Telnet(23)의 기본 포트 사용 가능, 그 외 포트는 1024-65535 범위 내에서 지정

2. 프로그램 실행
```bash
python network-device-inspection.py
```

3. 결과 확인
   - `inspection_results.xlsx`: 점검 결과
   - `backup/YYYYMMDD_HHMMSS/`: 설정 백업 파일
   - `session_logs/YYYYMMDD_HHMMSS/`: 세션 로그 파일
   - `logs/`: 프로그램 실행 로그

## 디렉토리 구조

```
.
├── backup/                    # 설정 백업 파일 저장
│   └── YYYYMMDD_HHMMSS/      # 실행별 백업 폴더
├── session_logs/             # 세션 로그 저장
│   └── YYYYMMDD_HHMMSS/      # 실행별 세션 로그 폴더
├── logs/                     # 프로그램 로그 저장
├── devices.xlsx              # 장비 정보 입력 파일
├── inspection_results.xlsx   # 점검 결과 파일
└── network-device-inspection.py  # 메인 프로그램
```

## 입력 데이터 검증

1. 엑셀 파일 검증
   - 필수 컬럼 존재 여부 확인
   - 빈 값 및 중복 IP 주소 확인
   - IP 주소 형식 검증
   - 포트 번호 범위 검증

2. 장비 정보 검증
   - 지원되는 벤더/모델 조합 확인
   - 접속 방식(ssh/telnet) 검증
   - 포트 번호 검증

## 로그 파일

1. 세션 로그 (`session_logs/YYYYMMDD_HHMMSS/`)
   - 파일명: `IP_vendor_model.log`
   - 연결 시도 및 명령어 실행 기록
   - 오류 발생 시 상세 정보 기록

2. 프로그램 로그 (`logs/`)
   - 파일명: `network_inspector_YYYYMMDD_HHMMSS.log`
   - 프로그램 실행 상태 및 오류 기록

## 지원하는 장비

- Cisco
  - IOS
  - IOS-XE
- Juniper
  - JunOS
- Ubiquoss
  - E4020

## 라이선스

MIT License 