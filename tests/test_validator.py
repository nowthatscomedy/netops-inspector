from __future__ import annotations

import pandas as pd
import pytest

from core.custom_exceptions import ValidationError
from core.validator import validate_dataframe, validate_device_info


def test_validate_device_info_success(sample_device: dict[str, object]) -> None:
    is_valid, message = validate_device_info(sample_device)
    assert is_valid is True
    assert message == ""


def test_validate_device_info_rejects_invalid_ip(sample_device: dict[str, object]) -> None:
    device = dict(sample_device)
    device["ip"] = "999.999.999.999"
    is_valid, message = validate_device_info(device)
    assert is_valid is False
    assert "999.999.999.999" in message


def test_validate_device_info_rejects_unknown_vendor(sample_device: dict[str, object]) -> None:
    device = dict(sample_device)
    device["vendor"] = "unknown-vendor"
    is_valid, message = validate_device_info(device)
    assert is_valid is False
    assert "unknown-vendor" in message


def test_validate_dataframe_raises_on_missing_required_column() -> None:
    df = pd.DataFrame(
        [
            {
                "ip": "192.0.2.10",
                "vendor": "cisco",
                "os": "ios",
                "connection_type": "ssh",
                "password": "pw",
            }
        ]
    )
    with pytest.raises(ValidationError):
        validate_dataframe(df)


def test_validate_dataframe_raises_on_duplicate_ip(sample_device: dict[str, object]) -> None:
    row = dict(sample_device)
    row.pop("username", None)
    row.pop("enable_password", None)
    df = pd.DataFrame([row, row])

    with pytest.raises(ValidationError) as exc_info:
        validate_dataframe(df)

    assert "192.0.2.10" in str(exc_info.value)


def test_validate_dataframe_aggregates_row_errors(sample_device: dict[str, object]) -> None:
    ok_row = dict(sample_device)
    bad_ip_row = dict(sample_device)
    bad_conn_row = dict(sample_device)
    for row in (ok_row, bad_ip_row, bad_conn_row):
        row.pop("username", None)
        row.pop("enable_password", None)
    bad_ip_row["ip"] = "bad-ip"
    bad_conn_row["ip"] = "192.0.2.99"
    bad_conn_row["connection_type"] = "http"

    df = pd.DataFrame([ok_row, bad_ip_row, bad_conn_row])

    with pytest.raises(ValidationError) as exc_info:
        validate_dataframe(df)

    message = str(exc_info.value)
    assert "bad-ip" in message
    assert "http" in message
