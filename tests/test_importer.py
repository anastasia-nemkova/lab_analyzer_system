"""Импорт с частичным успехом: accepted / duplicate / errors и номера строк"""

import json
import logging
from pathlib import Path

import pytest

from lab_analyzer.importer import ImportSummary, import_source
from lab_analyzer.repositories import InMemorySubmissionRepository
from lab_analyzer.services import SubmissionService
from lab_analyzer.sources import InMemorySource, JSONLSource
from tests.cases import RAW_EXAMPLE, changed


def _write(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_mixed_file_partial_success(
    tmp_path: Path, service: SubmissionService, repository: InMemorySubmissionRepository
) -> None:
    path = _write(
        tmp_path / "mixed.jsonl",
        [
            json.dumps(RAW_EXAMPLE),
            "{broken",
            json.dumps(RAW_EXAMPLE),
            json.dumps(changed(text="Другое содержимое с тем же ID")),
            json.dumps(changed(submission_id="bad-record", student_id="")),
            json.dumps(changed(submission_id="sub-002")),
        ],
    )
    summary = import_source(JSONLSource(path), service)
    assert summary.accepted == ["sub-001", "sub-002"]
    assert summary.duplicate == ["sub-001"]
    assert [(e["line_no"], e["code"]) for e in summary.errors] == [
        (2, "invalid_json"),
        (4, "conflict"),
        (5, "schema_error"),
    ]
    assert len(repository) == 2
    assert repository.get("bad-record") is None


def test_reimport_gives_only_duplicates(service: SubmissionService) -> None:
    values = [changed(submission_id=f"sub-{i}") for i in range(5)]
    first = import_source(InMemorySource(values), service)
    second = import_source(InMemorySource(values), service)
    assert len(first.accepted) == 5 and not first.errors
    assert len(second.duplicate) == 5 and not second.accepted and not second.errors


def test_summary_instances_do_not_share_lists() -> None:

    left, right = ImportSummary(), ImportSummary()
    left.errors.append({"code": "x"})
    assert right.errors == []


def test_logs_contain_no_source_code(
    service: SubmissionService, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="lab_analyzer"):
        import_source(InMemorySource([RAW_EXAMPLE, changed(student_id="")]), service)
    text = caplog.text
    assert "sub-001" in text
    assert str(RAW_EXAMPLE["code"]) not in text
    assert str(RAW_EXAMPLE["text"]) not in text


def test_unexpected_defect_is_not_swallowed(service: SubmissionService) -> None:
    class Boom:
        def accept(self, raw: object) -> None:
            raise RuntimeError("defect")

    with pytest.raises(RuntimeError):
        import_source(InMemorySource([RAW_EXAMPLE]), Boom())


def test_successful_record_is_not_reported_as_error(service: SubmissionService) -> None:
    summary = import_source(InMemorySource([RAW_EXAMPLE]), service)
    assert summary.accepted == ["sub-001"]
    assert summary.errors == []


def test_error_is_not_repeated_after_following_success(service: SubmissionService) -> None:
    values = [changed(student_id=""), changed(submission_id="sub-002")]
    summary = import_source(InMemorySource(values), service)
    assert [e["line_no"] for e in summary.errors] == [1]
    assert summary.accepted == ["sub-002"]


def test_importer_logs_results(
    service: SubmissionService, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="lab_analyzer"):
        import_source(InMemorySource([RAW_EXAMPLE, changed(student_id="")]), service)
    assert "result=accepted" in caplog.text
    assert "code=schema_error" in caplog.text
