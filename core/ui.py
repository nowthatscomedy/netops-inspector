import msvcrt
import sys


def get_password_from_cli() -> str | None:
    """콘솔에서 비밀번호를 마스킹(*)하여 입력받습니다."""
    sys.stdout.write(">> 암호화된 파일의 비밀번호를 입력하세요: ")
    sys.stdout.flush()
    password = ""

    while True:
        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            print()
            return password if password else None
        if key == "\x08":
            if password:
                password = password[:-1]
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue
        if key in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue
        password += key
        sys.stdout.write("*")
        sys.stdout.flush()
