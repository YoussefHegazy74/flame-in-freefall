"""Unit tests for shared parsing contracts and sentinel classification."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.data_pipeline.parsers.base import (
    HeaderMismatchError,
    categorical,
    decode_bytes,
    excel_serial_to_date,
    iso_date,
    pad_row,
    parse_int,
    parse_number,
    require_exact_header,
    row_is_empty,
)


@pytest.mark.parametrize(
    ("raw", "value", "flag"),
    [
        (0, 0.0, "ok"),
        (1.25, 1.25, "ok"),
        ("0.207128374", 0.207128374, "ok"),
        ("-7.53E-05", -7.53e-05, "ok"),
        ("1,234.5", 1234.5, "thousands_separator"),
        ("-999", -999.0, "ok"),
    ],
)
def test_parse_number_numeric(raw, value, flag):
    parsed = parse_number(raw)
    assert parsed.value == pytest.approx(value)
    assert parsed.flag == flag


@pytest.mark.parametrize(
    ("raw", "flag"),
    [
        ("", "missing"),
        (None, "missing"),
        ("-", "sentinel_dash"),
        ("--", "sentinel_dash"),
        ("–", "sentinel_dash"),
        ("—", "sentinel_dash"),
        ("RAMP", "ramped_condition"),
        ("RAMPED", "ramped_condition"),
        ("LOW O2", "low_oxygen_condition"),
        ("N/A", "not_applicable"),
        ("none", "not_measured"),
        ("OR", "over_range"),
        ("NaN", "missing"),
        ("#VALUE!", "spreadsheet_error"),
        ("#DIV/0!", "spreadsheet_error"),
        ("#N/A", "spreadsheet_error"),
        ("-1.#IND", "invalid_indefinite"),
        ("1.#INF", "invalid_indefinite"),
        ("<0.1", "inequality_text"),
        ("1.2-1.4", "range_text"),
        ("1.2;1.4", "range_text"),
        ("5 mg/s", "unit_text"),
        ("Yes", "non_numeric"),
        ("not a number", "non_numeric"),
    ],
)
def test_parse_number_non_numeric(raw, flag):
    parsed = parse_number(raw)
    assert parsed.value is None
    assert parsed.flag == flag
    assert parsed.raw == (None if raw is None else str(raw))


def test_parse_number_approximate_and_percent_keep_value():
    approximate = parse_number("~5.0")
    assert approximate.value == pytest.approx(5.0)
    assert approximate.flag == "approximate"

    percent = parse_number("50%")
    assert percent.value == pytest.approx(50.0)
    assert percent.flag == "percent_text"


def test_parse_number_boolean_and_datetime_are_not_measurements():
    boolean = parse_number(True)
    assert boolean.value == 1.0
    assert boolean.flag == "boolean"

    timestamp = parse_number(datetime(2026, 11, 9, 12, 0, 0))
    assert timestamp.value is None
    assert timestamp.flag == "datetime_value"


def test_parse_number_nan_and_infinity():
    assert parse_number(float("nan")).flag == "missing"
    assert parse_number(float("inf")).flag == "invalid_infinite"


def test_parse_int_requires_an_integer():
    assert parse_int("3") == (3, "ok")
    assert parse_int("3.5") == (None, "non_integer")
    assert parse_int("RAMP") == (None, "ramped_condition")
    assert parse_int("") == (None, "missing")


def test_categorical_keeps_text_and_flags_missing_tokens():
    assert categorical("  Yes  ") == ("Yes", "ok")
    assert categorical("") == (None, "missing")
    assert categorical("-") == (None, "sentinel_dash")
    assert categorical("none") == (None, "not_available")
    assert categorical(None) == (None, "missing")


def test_decode_bytes_utf8_and_cp1252():
    text, encoding, fallback = decode_bytes("café".encode("utf-8"))
    assert (text, encoding, fallback) == ("café", "utf-8", False)

    text, encoding, fallback = decode_bytes(b"caf\xe9")
    assert text == "café"
    assert encoding == "cp1252"
    assert fallback is True

    text, encoding, fallback = decode_bytes(b"a \x96 b")
    assert text == "a – b"
    assert encoding == "cp1252"
    assert fallback is True
    assert "\ufffd" not in text


def test_decode_bytes_strips_utf8_bom():
    text, encoding, fallback = decode_bytes(b"\xef\xbb\xbfheader")
    assert text == "header"
    assert encoding == "utf-8-sig"
    assert fallback is False


def test_require_exact_header_accepts_exact_and_rejects_drift(source_factory, fixtures_dir):
    source = source_factory(fixtures_dir / "psi10_normal_sentinels.csv")
    require_exact_header(["a", "b"], ["a", "b"], source)
    with pytest.raises(HeaderMismatchError, match="column 1"):
        require_exact_header(["a", "c"], ["a", "b"], source)
    with pytest.raises(HeaderMismatchError, match="actual 1 columns, expected 2"):
        require_exact_header(["a"], ["a", "b"], source)


def test_pad_row_and_row_is_empty():
    assert pad_row([1, 2], 3) == ([1, 2, None], "short_row")
    assert pad_row([1, 2, 3], 3) == ([1, 2, 3], None)
    assert pad_row([1, 2, 3, 4], 3) == ([1, 2, 3, 4], "long_row")
    assert row_is_empty([None, "", "  "]) is True
    assert row_is_empty([0]) is False
    assert row_is_empty(["", "x"]) is False


def test_iso_date_variants():
    assert iso_date("2021-05-06") == ("2021-05-06", "ok")
    assert iso_date("5/6/2021") == ("2021-05-06", "ok")
    assert iso_date("06-May-21") == ("2021-05-06", "ok")
    assert iso_date(date(2021, 5, 6)) == ("2021-05-06", "ok")
    assert iso_date(datetime(2021, 5, 6, 12, 0, 0)) == ("2021-05-06", "ok")
    assert iso_date("not a date") == (None, "unparsed_date")
    assert iso_date("") == (None, "missing")


def test_excel_serial_dates_use_an_explicit_epoch():
    assert excel_serial_to_date(44197, datemode=0) == "2021-01-01"
    assert excel_serial_to_date(44197, datemode=1) == "2025-01-02"
    assert excel_serial_to_date(0) is None
    assert excel_serial_to_date(True) is None
