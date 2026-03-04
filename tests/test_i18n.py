from __future__ import annotations

from core.i18n import get_locale, normalize_language_code, set_locale, t


def test_normalize_language_code_handles_case_and_separator() -> None:
    assert normalize_language_code("EN") == "en"
    assert normalize_language_code("pt_br") == "pt-BR"
    assert normalize_language_code("zh-cn") == "zh-CN"
    assert normalize_language_code("unknown") == "en"


def test_set_locale_updates_active_and_fallback() -> None:
    set_locale("ko", "en")
    assert get_locale() == ("ko", "en")


def test_translate_returns_korean_text_when_locale_is_ko() -> None:
    set_locale("ko", "en")
    assert t("main.shutdown") == "프로그램을 종료합니다."


def test_translate_falls_back_to_english_when_locale_file_is_missing() -> None:
    set_locale("ja", "en")
    assert t("main.shutdown") == "Program terminated."


def test_translate_returns_key_when_message_is_missing() -> None:
    set_locale("en", "en")
    assert t("missing.translation.key") == "missing.translation.key"
