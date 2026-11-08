"""Downloader safety, selection, verification, and local-HTTP tests."""

from __future__ import annotations

import hashlib
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import src.data_pipeline.downloader as downloader
from src.data_pipeline.downloader import (
    AcquisitionReport,
    DownloadLimitError,
    DownloadResult,
    KnownUnavailableResult,
    UnsafePathError,
    _duplicate_checksums,
    _existing_result,
    _parse_content_range,
    check_limits,
    download_one,
    safe_target_path,
    select_entries,
    verify_known_unavailable,
)
from src.data_pipeline.manifest import build_manifest, download_url


def entry_for(payload: bytes, url: str, *, expected_sha: str | None = None) -> dict:
    return {
        "file_id": "PSI-10::sample.bin",
        "accession": "PSI-10",
        "file_name": "sample.bin",
        "expected_bytes": len(payload),
        "sha256_expected": expected_sha if expected_sha is not None else hashlib.sha256(payload).hexdigest(),
        "source_url": url,
    }


class PayloadHandler(BaseHTTPRequestHandler):
    payload = b""

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/missing"):
            self.send_error(404, "Not Found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):  # noqa: A002
        pass


@pytest.fixture
def http_server():
    PayloadHandler.payload = b"authentic test payload\n"
    server = ThreadingHTTPServer(("127.0.0.1", 0), PayloadHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_download_one_verifies_size_and_checksum(http_server, tmp_path):
    payload = PayloadHandler.payload
    entry = entry_for(payload, f"{http_server}/sample.bin")
    result = download_one(entry, raw_dir=tmp_path, retries=1, backoff=0, rate_limit=0)
    assert result.status == "downloaded"
    assert result.http_status == 200
    assert result.bytes_downloaded == len(payload)
    assert result.sha256_actual == hashlib.sha256(payload).hexdigest()
    assert result.retrieved_at
    target = tmp_path / "PSI-10" / "sample.bin"
    assert target.read_bytes() == payload
    assert not target.with_name("sample.bin.part").exists()


def test_download_one_rejects_a_checksum_mismatch(http_server, tmp_path):
    entry = entry_for(
        PayloadHandler.payload,
        f"{http_server}/sample.bin",
        expected_sha="0" * 64,
    )
    result = download_one(entry, raw_dir=tmp_path, retries=1, backoff=0, rate_limit=0)
    assert result.status == "failed"
    assert "checksum mismatch" in result.error
    assert not (tmp_path / "PSI-10" / "sample.bin").exists()


def test_download_one_records_a_listed_404(http_server, tmp_path):
    entry = entry_for(b"x", f"{http_server}/missing.bin")
    result = download_one(entry, raw_dir=tmp_path, retries=1, backoff=0, rate_limit=0)
    assert result.status == "listed_404"
    assert result.http_status == 404
    assert result.error


def test_download_one_does_not_redownload_a_verified_existing_file(tmp_path):
    payload = b"existing verified bytes"
    entry = entry_for(payload, "http://127.0.0.1:1/unused")
    target = tmp_path / "PSI-10" / "sample.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    result = download_one(entry, raw_dir=tmp_path, retries=1, backoff=0, rate_limit=0)
    assert result.status == "already_present"
    assert result.sha256_actual == hashlib.sha256(payload).hexdigest()
    assert target.read_bytes() == payload


def test_existing_result_detects_size_and_checksum_drift(tmp_path):
    entry = entry_for(b"abc", "http://example.invalid")
    target = tmp_path / "PSI-10" / "sample.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"ab")
    result = _existing_result(entry, target)
    assert result.status == "failed"
    assert "size" in result.error

    target.write_bytes(b"abc")
    result = _existing_result({**entry, "sha256_expected": "0" * 64}, target)
    assert result.status == "failed"
    assert "checksum" in result.error

    assert _existing_result(entry, tmp_path / "missing.bin") is None


def test_safe_target_path_rejects_escape_attempts(tmp_path):
    assert safe_target_path(tmp_path, "PSI-10", "file.csv") == (
        tmp_path / "PSI-10" / "file.csv"
    ).resolve()
    for accession, file_name in (
        ("../PSI-10", "file.csv"),
        ("PSI-10", "../file.csv"),
        ("PSI-10", "a/b.csv"),
        ("PSI-10", "a\\b.csv"),
        ("PSI-10", ".."),
        ("PSI-10", ""),
    ):
        with pytest.raises(UnsafePathError):
            safe_target_path(tmp_path, accession, file_name)


def test_select_entries_by_accession():
    manifest = {
        "files": [
            {"accession": "PSI-10", "file_id": "a"},
            {"accession": "PSI-100", "file_id": "b"},
            {"accession": "PSI-100", "file_id": "c"},
        ]
    }
    assert [item["file_id"] for item in select_entries(manifest, None)] == ["a", "b", "c"]
    assert [item["file_id"] for item in select_entries(manifest, ["all"])] == ["a", "b", "c"]
    assert [item["file_id"] for item in select_entries(manifest, ["PSI-100"])] == ["b", "c"]
    with pytest.raises(downloader.DownloadError, match="not present"):
        select_entries(manifest, ["PSI-999"])


def test_check_limits_enforces_hard_caps():
    entries = [
        {"file_id": "a", "expected_bytes": 10},
        {"file_id": "b", "expected_bytes": 20},
    ]
    assert check_limits(entries, max_single_file_bytes=15, max_total_bytes=100, max_files=2) == [entries[1]]
    assert check_limits(
        entries,
        max_single_file_bytes=15,
        max_total_bytes=100,
        max_files=2,
        allow_large=True,
    ) == []
    with pytest.raises(DownloadLimitError, match="max_files"):
        check_limits(entries, max_single_file_bytes=100, max_total_bytes=100, max_files=1)
    with pytest.raises(DownloadLimitError, match="max_total_bytes"):
        check_limits(entries, max_single_file_bytes=100, max_total_bytes=10, max_files=2)


def test_parse_content_range():
    assert _parse_content_range("bytes 0-99/100") == 100
    assert _parse_content_range("bytes 0-99/*") is None
    assert _parse_content_range("garbage") is None
    assert _parse_content_range(None) is None


def test_acquisition_report_summary_counts_statuses():
    report = AcquisitionReport(
        schema_version="1.0.0",
        generated_at="2026-11-09T00:00:00Z",
        manifest="data/registry/download_manifest.json",
        selected_datasets=["PSI-10"],
        selected_files=3,
        selected_bytes=30,
        limits={},
        disk_free_before=1,
        disk_free_after=2,
        results=[
            DownloadResult("a", "PSI-10", "a", "downloaded", bytes_downloaded=10),
            DownloadResult("b", "PSI-10", "b", "already_present", bytes_downloaded=10),
            DownloadResult("c", "PSI-10", "c", "listed_404", bytes_downloaded=0),
        ],
        known_unavailable=[
            KnownUnavailableResult("PSI-98", "x", 404, 404, "listed_404"),
        ],
    )
    summary = report.summary()
    assert summary["downloaded"] == 1
    assert summary["already_present"] == 1
    assert summary["listed_404"] == 1
    assert summary["failed"] == 0
    assert summary["total_bytes_downloaded"] == 10
    assert summary["known_unavailable_verified"] == 1


def test_duplicate_checksums_ignore_failed_results():
    results = [
        DownloadResult("a", "PSI-10", "a", "downloaded", sha256_actual="x" * 64),
        DownloadResult("b", "PSI-10", "b", "already_present", sha256_actual="x" * 64),
        DownloadResult("c", "PSI-10", "c", "failed", sha256_actual="x" * 64),
    ]
    groups = _duplicate_checksums(results)
    assert groups == [{"sha256": "x" * 64, "file_ids": ["a", "b"]}]


class _FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def getcode(self):
        return self.status

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False


def test_verify_known_unavailable_handles_404_and_unexpected_availability(monkeypatch):
    manifest = {
        "known_unavailable": [
            {"accession": "PSI-98", "file_name": "missing.xlsx", "expected_status": 404}
        ]
    }

    def not_found(*args, **kwargs):
        raise urllib.error.HTTPError("http://example", 404, "Not Found", None, None)

    monkeypatch.setattr(downloader, "_open_url", not_found)
    result = verify_known_unavailable(manifest, timeout=1)
    assert result[0].status == "listed_404"
    assert result[0].observed_status == 404

    monkeypatch.setattr(downloader, "_open_url", lambda *args, **kwargs: _FakeResponse(200))
    result = verify_known_unavailable(manifest, timeout=1)
    assert result[0].status == "unexpectedly_available"
    assert result[0].observed_status == 200


def test_committed_manifest_urls_are_built_from_the_verified_endpoint():
    manifest = build_manifest()
    for item in manifest["files"]:
        assert item["source_url"] == download_url(item["accession"], item["file_name"])
