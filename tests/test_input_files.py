"""Входные файлы задания: submissions.jsonl, invalid_submissions.jsonl, assignments.json"""

import json
from pathlib import Path

from lab_analyzer.app import build_application
from lab_analyzer.config import DEFAULT_CONFIG
from lab_analyzer.importer import import_source
from lab_analyzer.models import Assignment
from lab_analyzer.sources import JSONLSource

DATA = Path(__file__).resolve().parent.parent / "data"


def test_invalid_file_gives_expected_outcome_per_line() -> None:
    app = build_application()
    summary = import_source(JSONLSource(DATA / "invalid_submissions.jsonl"), app.submission_service)
    assert summary.accepted == ["inv-001", "inv-015"]
    assert summary.duplicate == ["inv-001"]
    assert [(e["line_no"], e["code"], e["field"]) for e in summary.errors] == [
        (2, "invalid_json", "json"),  # повреждённый JSON
        (3, "invalid_json", "student_id"),  # повтор ключа
        (4, "invalid_json", "json"),  # NaN
        (5, "invalid_json", "json"),  # не объект
        (6, "schema_error", "code"),  # неверный тип
        (7, "schema_error", "submitted_at"),  # время без часового пояса
        (8, "schema_error", "student_id"),  # пустой идентификатор
        (9, "schema_error", "unknown"),  # неизвестное поле
        (10, "unsupported_version", "schema_version"),
        (11, "schema_error", "ai_declaration"),  # used=true без tool/purpose
        (13, "conflict", "submission_id"),  # тот же id, другое содержимое
        (14, "invalid_json", "json"),  # пустая строка
    ]


def test_invalid_file_keeps_first_version_after_conflict() -> None:
    app = build_application()
    import_source(JSONLSource(DATA / "invalid_submissions.jsonl"), app.submission_service)
    stored = app.repository.get("inv-001")
    assert stored is not None and "Другая версия" not in stored.text
    assert app.repository.get("inv-006") is None 
    assert len(app.repository) == 2


def test_valid_record_after_errors_is_still_processed() -> None:
    app = build_application()
    summary = import_source(JSONLSource(DATA / "invalid_submissions.jsonl"), app.submission_service)
    assert "inv-015" in summary.accepted


def test_assignments_file_matches_default_config_and_corpus() -> None:
    data = json.loads((DATA / "assignments.json").read_text(encoding="utf-8"))
    items = {a["assignment_id"]: a for a in data["assignments"]}
    first = items["assignment-01"]
    assert Assignment(
        first["assignment_id"], first["allowed_template"], tuple(first["requirements"])
    ) == DEFAULT_CONFIG.assignment
    for line in (DATA / "submissions.jsonl").read_text(encoding="utf-8").splitlines():
        assert json.loads(line)["assignment_id"] in items
