"""Canonical Arrow schema and Parquet I/O tests."""

from __future__ import annotations

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.data_pipeline.config import CANONICAL_SCHEMA_JSON
from src.data_pipeline.schemas import (
    PRIMARY_KEYS,
    TABLE_SCHEMAS,
    concat_parquet,
    normalize_records,
    schema_report,
    write_parquet,
    write_parquet_batches,
    write_schema_report,
)


def test_every_canonical_table_has_a_schema_and_primary_key():
    assert len(TABLE_SCHEMAS) == 13
    assert set(TABLE_SCHEMAS) == set(PRIMARY_KEYS)
    for table_name, schema in TABLE_SCHEMAS.items():
        assert PRIMARY_KEYS[table_name] in schema.names, table_name
        assert len(schema.names) == len(set(schema.names)), table_name


def test_schema_report_matches_the_committed_registry():
    report = schema_report()
    committed = json.loads(CANONICAL_SCHEMA_JSON.read_text(encoding="utf-8"))
    assert committed == report
    assert report["schema_version"] == "1.0.0"
    assert len(report["tables"]) == 13
    for table in report["tables"].values():
        assert table["description"]
        assert table["primary_key"]
        assert table["columns"]
        assert all(column["name"] and column["type"] for column in table["columns"])


def test_write_schema_report_is_deterministic(tmp_path):
    path = tmp_path / "canonical_schema.json"
    write_schema_report(path)
    first = path.read_text(encoding="utf-8")
    write_schema_report(path)
    assert path.read_text(encoding="utf-8") == first
    assert json.loads(first) == schema_report()


def test_normalize_records_fills_nulls_and_drops_undeclared_fields():
    schema = pa.schema([pa.field("a", pa.string()), pa.field("b", pa.int64())])
    normalized = normalize_records([{"a": "x", "extra": 1}, {"b": 2}], schema)
    assert normalized == [{"a": "x", "b": None}, {"a": None, "b": 2}]


def test_parquet_round_trip_and_schema(tmp_path):
    path = tmp_path / "psi_investigation.parquet"
    record = {
        "accession": "PSI-10",
        "acronym": "ACME/Flame Design",
        "title": "Advanced Combustion via Microgravity Experiments / Flame Design",
        "public": True,
        "restricted": False,
        "version": 1,
        "file_count": 3807,
        "limitations_json": "[]",
    }
    result = write_parquet([record], "psi_investigation", path)
    assert result.rows == 1
    assert result.bytes == path.stat().st_size

    table = pq.read_table(path)
    assert table.schema.equals(TABLE_SCHEMAS["psi_investigation"], check_metadata=False)
    assert table.to_pylist()[0]["accession"] == "PSI-10"
    assert table.to_pylist()[0]["file_count"] == 3807


def test_parquet_batches_and_concat(tmp_path):
    schema = pa.schema([pa.field("a", pa.string())])
    first = tmp_path / "first.parquet"
    second = tmp_path / "second.parquet"
    combined = tmp_path / "combined.parquet"

    first_result = write_parquet_batches(
        [[{"a": "1"}, {"a": "2"}], [{"a": "3"}]],
        "psi_investigation",
        first,
        schema=schema,
    )
    second_result = write_parquet_batches(
        [[{"a": "4"}]],
        "psi_investigation",
        second,
        schema=schema,
    )
    assert first_result.rows == 3
    assert second_result.rows == 1

    result = concat_parquet([first, second], "psi_investigation", combined, schema=schema)
    assert result.rows == 4
    assert pq.read_table(combined).column("a").to_pylist() == ["1", "2", "3", "4"]


def test_concat_parquet_fails_on_missing_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        concat_parquet(
            [tmp_path / "missing.parquet"],
            "psi_investigation",
            tmp_path / "out.parquet",
        )


def test_unknown_table_name_fails_closed(tmp_path):
    with pytest.raises(KeyError):
        write_parquet([], "not_a_table", tmp_path / "x.parquet")
    with pytest.raises(KeyError):
        write_parquet_batches([], "not_a_table", tmp_path / "x.parquet")


def test_all_schema_fields_are_nullable_and_typed():
    for schema in TABLE_SCHEMAS.values():
        for field in schema:
            assert field.nullable is True
            assert field.type is not None
