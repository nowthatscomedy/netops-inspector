# Network Device Inspection

네트워크 장비 점검 및 설정 백업을 자동화하는 프로그램입니다.

## 주요 기능

- 엑셀 파일(`devices.xlsx`)을 통한 장비 정보 입력
- SSH/Telnet을 통한 장비 접속 (연결 실패 시 최대 3번 재시도)
- 장비별 점검 명령어 실행 및 결과 수집
- 설정 파일 백업 및 세션 로그 저장
- 결과를 엑셀 파일(`inspection_results.xlsx`)로 저장
- 점검만 또는 백업만 선택적으로 실행 가능

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
   - 필수 컬럼: ip, vendor, OS, connection_type, port, password
   - 선택 컬럼: username (레거시 Cisco 장비와 같이 username을 사용하지 않는 장비의 경우 빈 값 허용)
   - connection_type: ssh 또는 telnet
   - port: SSH(22) 또는 Telnet(23)의 기본 포트 사용 가능, 그 외 포트는 1024-65535 범위 내에서 지정

2. 프로그램 실행
```bash
python network-device-inspection.py
```

3. 실행 옵션 선택
   - 1: 점검만 실행
   - 2: 백업만 실행
   - 3: 점검과 백업 모두 실행

4. 결과 확인
   - `inspection_results_YYYYMMDD_HHMMSS.xlsx`: 점검 결과
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
├── inspection_results_YYYYMMDD_HHMMSS.xlsx   # 점검 결과 파일
├── network-device-inspection.py  # 메인 프로그램
├── device_commands.py        # 장비별 명령어 정의 및 파싱 규칙
└── custom_device_handlers.py # 커스텀 장비 핸들러
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
  - Legacy (username 없이 password만으로 접속하는 레거시 장비)
- Juniper
  - JunOS (SRX 시리즈 등 모든 Juniper 장비)
- Ubiquoss
  - E4020
- Axgate
  - Axgate
- NexG
  - VForce

## 최근 변경 사항

- 필수 컬럼 명칭을 'model'에서 'OS'로 변경
- 레거시 Cisco 스위치 지원 추가 (username 없이 password만으로 접속)
- username 필드를 필수가 아닌 선택적 필드로 변경
- Juniper SRX300 모델을 JunOS로 통일하여 모든 Juniper 장비에 대한 일관된 처리 지원
- Axgate-80D 모델을 Axgate로 통일하여 Axgate 장비 처리 간소화
- 파싱 결과 중복 문제 해결 (특히 Juniper 장비에서 first_match_only 옵션 추가)
- 점검 또는 백업 모드만 단독으로 실행 시 불필요한 명령어 실행 방지
- 다양한 Juniper 장비 모델에 대한 파싱 패턴 개선

## 라이선스

MIT License 