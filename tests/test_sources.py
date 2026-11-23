"""Контрактные тесты источников: порядок, номера строк, данные и жизненный цикл ресурса"""

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from lab_analyzer.errors import INVALID_JSON
from lab_analyzer.sources import InMemorySource, JSONLSource, StreamSource, SubmissionSource
from tests.cases import RAW_EXAMPLE, changed

VALUES: list[dict[str, Any]] = [
    changed(submission_id="sub-001"),
    changed(submission_id="sub-002"),
    changed(submission_id="sub-003"),
]


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values)


def _make_memory() -> SubmissionSource:
    return InMemorySource(VALUES)


@pytest.fixture
def jsonl_path(tmp_path: Path) -> Path:
    path = tmp_path / "data.jsonl"
    path.write_text(_jsonl(VALUES), encoding="utf-8")
    return path


def _make_file_factory(path: Path) -> Callable[[], SubmissionSource]:
    return lambda: JSONLSource(path)


def _make_stream() -> SubmissionSource:
    return StreamSource(io.StringIO(_jsonl(VALUES)))


@pytest.fixture(params=["memory", "file", "stream"])
def source(request: pytest.FixtureRequest, jsonl_path: Path) -> SubmissionSource:
    factories: dict[str, Callable[[], SubmissionSource]] = {
        "memory": _make_memory,
        "file": _make_file_factory(jsonl_path),
        "stream": _make_stream,
    }
    return factories[request.param]()


def test_contract_order_numbers_and_data(source: SubmissionSource) -> None:
    with source.open() as records:
        loaded = list(records)
    assert [r.line_no for r in loaded] == [1, 2, 3]
    assert [r.raw for r in loaded] == VALUES
    assert all(r.error is None for r in loaded)


def test_in_memory_source_yields_copies() -> None:
    src = InMemorySource(VALUES)
    with src.open() as records:
        first = next(records)
    assert first.raw is not None
    first.raw["student_id"] = "mutated"
    with src.open() as records:
        again = next(records)
    assert again.raw == VALUES[0]
    assert VALUES[0]["student_id"] == RAW_EXAMPLE["student_id"]


def test_file_closed_after_full_read(jsonl_path: Path) -> None:
    src = JSONLSource(jsonl_path)
    with src.open() as records:
        list(records)
    assert src.last_closed is True


def test_file_closed_on_early_exit(jsonl_path: Path) -> None:
    src = JSONLSource(jsonl_path)
    with src.open() as records:
        next(records)
    assert src.last_closed is True


def test_file_closed_on_consumer_exception_and_error_propagates(jsonl_path: Path) -> None:
    src = JSONLSource(jsonl_path)
    with pytest.raises(RuntimeError, match="boom"), src.open() as records:
        next(records)
        raise RuntimeError("boom")
    assert src.last_closed is True


def test_missing_file_raises_oserror_not_record_error(tmp_path: Path) -> None:
    src = JSONLSource(tmp_path / "absent.jsonl")
    with pytest.raises(FileNotFoundError), src.open():
        pass


def test_broken_line_is_record_error_and_reading_continues(tmp_path: Path) -> None:
    path = tmp_path / "mixed.jsonl"
    good = json.dumps(VALUES[0], ensure_ascii=False)
    path.write_text(f"{good}\n{{broken\n\n{good}\n", encoding="utf-8")
    with JSONLSource(path).open() as records:
        loaded = list(records)
    assert [r.line_no for r in loaded] == [1, 2, 3, 4]
    assert loaded[0].error is None
    assert loaded[1].error is not None and loaded[1].error.code == INVALID_JSON
    assert loaded[2].error is not None and loaded[2].error.code == INVALID_JSON  # пустая строка
    assert loaded[3].error is None


def test_non_object_json_line_is_record_error() -> None:
    with StreamSource(io.StringIO("[1, 2]\n")).open() as records:
        loaded = list(records)
    assert loaded[0].error is not None
    assert loaded[0].error.code == INVALID_JSON


def test_stream_source_does_not_close_caller_stream() -> None:
    stream = io.StringIO(_jsonl(VALUES))
    with StreamSource(stream).open() as records:
        list(records)
    assert stream.closed is False
