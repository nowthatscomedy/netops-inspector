# 네트워크 장비 점검 자동화 프로그램

이 프로그램은 여러 네트워크 장비에 동시에 접속하여 점검 명령어를 실행하고, 결과를 파싱하여 엑셀 파일로 저장하는 자동화 도구입니다.

## 주요 기능

- 여러 네트워크 장비에 동시 접속
- 벤더/모델/버전별 맞춤 명령어 실행
- 명령어 결과 자동 파싱
- 설정 백업 자동화
- 결과를 엑셀 파일로 저장

## 설치 방법

1. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

2. 입력 엑셀 파일(`devices.xlsx`) 준비:
   - 벤더사
   - 모델명
   - 버전
   - 장비IP
   - 접속방식(ssh/telnet)
   - port
   - username
   - password
   - enable password(선택)

## 사용 방법

1. `devices.xlsx` 파일에 점검할 장비 정보를 입력합니다.
2. 프로그램을 실행합니다:
```bash
python network_inspector.py
```
3. 결과는 `inspection_results.xlsx` 파일에 저장됩니다.
4. 설정 백업 파일은 `backup_[IP]_[timestamp].txt` 형식으로 저장됩니다.

## 주의사항

- 장비 접속 정보는 안전하게 관리해야 합니다.
- 대량의 장비를 동시에 점검할 경우 네트워크 부하를 고려해야 합니다.
- 새로운 장비 타입을 추가하려면 `device_commands.py` 파일을 수정해야 합니다. 