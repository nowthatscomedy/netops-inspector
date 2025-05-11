# Network Device Inspection

네트워크 장비 점검 및 설정 백업을 자동화하는 프로그램입니다.

## 주요 기능

- 다중 장비 동시 점검
- 장비별 설정 백업
- 세션 로그 자동 저장
- 엑셀 파일 기반 장비 정보 관리
- 실패 시 자동 재시도 (지수 백오프 적용)
- 메모리 사용량 모니터링

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/ch0c0l8/network-device-inspection.git
cd network-device-inspection
```

2. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

## 사용 방법

1. 장비 정보 입력
   - `devices.xlsx` 파일에 장비 정보 입력
   - 필수 컬럼: ip, vendor, model, version, connection_type, port, username, password
   - 칼럼 순서는 상관없음 (대소문자 구분 없음)

2. 프로그램 실행
```bash
python network-device-inspection.py
```

3. 결과 확인
   - 점검 결과: `inspection_results.xlsx`
   - 설정 백업: `backup_YYYYMMDD_HHMMSS/` 디렉토리
   - 세션 로그: `session_logs_YYYYMMDD_HHMMSS/` 디렉토리

## 로그 파일 구조

```
session_logs_YYYYMMDD_HHMMSS/
├── 192.168.1.1_cisco_2960_15.0.log
├── 192.168.1.2_cisco_3850_16.9.log
└── 192.168.1.3_hp_5120_7.1.log
```

## 주요 특징

1. **데이터 검증**
   - 엑셀 파일 형식 검증
   - IP 주소 형식 검증
   - 포트 번호 범위 검증 (1-65535)
   - 빈 값 및 중복 데이터 검증

2. **에러 처리**
   - 연결 실패 시 최대 3번 재시도
   - 지수 백오프 적용 (2초 → 4초 → 8초)
   - 상세한 에러 로그 기록

3. **리소스 관리**
   - 메모리 사용량 모니터링
   - CPU 코어 수에 따른 최적 작업자 수 설정
   - 로그 파일 크기 제한 (10MB)

4. **로그 관리**
   - 장비별 통합 세션 로그
   - 시간순 정렬된 로그 기록
   - 로그 파일 자동 로테이션

## 지원하는 장비

- Cisco 장비
- HP 장비
- 기타 Netmiko에서 지원하는 장비

## 주의사항

1. 장비 정보 입력 시
   - IP 주소는 유효한 형식이어야 함
   - 포트 번호는 1024-65535 범위 내에서만 사용 가능
   - SSH(22)와 Telnet(23) 기본 포트는 예외적으로 사용 가능
   - 그 외 잘 알려진 포트(1-1023)는 시스템 예약 포트로 사용 불가
   - 벤더/모델/버전은 지원되는 조합이어야 함

2. 프로그램 실행 시
   - 충분한 디스크 공간 확보
   - 네트워크 연결 상태 확인
   - 방화벽 설정 확인
   - SSH/Telnet 접속 시 가능한 비표준 포트 사용 권장

## 라이선스

MIT License

## 기여 방법

1. Fork the Project
2. Create your Feature Branch
3. Commit your Changes
4. Push to the Branch
5. Open a Pull Request 