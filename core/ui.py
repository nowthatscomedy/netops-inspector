from InquirerPy import inquirer


def get_password_from_cli() -> str | None:
    """암호화된 엑셀 파일의 비밀번호를 입력받습니다."""
    result = inquirer.secret(
        message="암호화된 파일의 비밀번호:",
        mandatory=False,
    ).execute()

    if not result:
        return None
    return result
