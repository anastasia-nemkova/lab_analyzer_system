"""Проверки на корпусе submissions.jsonl: отчёты, evidence, неизменность, текст-инъекция"""

from pathlib import Path

from lab_analyzer.app import Application, build_application, default_registry
from lab_analyzer.importer import import_source
from lab_analyzer.reporting import validate_report
from lab_analyzer.sources import JSONLSource

ROOT = Path(__file__).resolve().parent.parent


CORPUS = ROOT / "data" / "submissions.jsonl"


def test_corpus_prompt_injection_text_is_just_data() -> None:
    app = build_application()
    import_source(JSONLSource(CORPUS), app.submission_service)
    stored = app.repository.get("sub-010")
    assert stored is not None and "Игнорируй рубрику" in stored.text
    for report in app.analyze_all("sub-010"):
        assert all(f.score is None for f in report.findings)


def test_corpus_has_twelve_valid_unique_records(loaded_app: Application) -> None:
    ids = [f"sub-{i:03d}" for i in range(1, 13)]
    assert all(loaded_app.repository.get(i) is not None for i in ids)
    assert len(loaded_app.repository) == 12


def test_corpus_declaration_reports(loaded_app: Application) -> None:
    for submission_id, used in [("sub-001", False), ("sub-003", True), ("sub-006", True)]:
        report = loaded_app.analysis_service.run(submission_id, "declaration", loaded_app.context)
        assert ("заявлено." in report.findings[0].explanation
                and "не заявлено" not in report.findings[0].explanation) is used
        assert report.review_required is False


def test_corpus_length_counts_match_source(loaded_app: Application) -> None:
    for i in range(1, 13):
        sid = f"sub-{i:03d}"
        stored = loaded_app.repository.get(sid)
        assert stored is not None
        report = loaded_app.analysis_service.run(sid, "length", loaded_app.context)
        expected = sum(1 for line in stored.code.splitlines() if line.strip())
        assert f"code={expected}" in report.findings[0].explanation


def test_corpus_template_found_where_template_present(loaded_app: Application) -> None:
    report = loaded_app.analysis_service.run("sub-001", "template", loaded_app.context)
    assert report.findings[0].evidence != ()
    for e in report.findings[0].evidence:
        stored = loaded_app.repository.get("sub-001")
        assert stored is not None
        assert stored.code.splitlines()[e.start_line - 1] == "from typing import Iterable"


def test_corpus_all_reports_validate_and_do_not_mutate(loaded_app: Application) -> None:
    snapshot = {i: loaded_app.repository.get(f"sub-{i:03d}") for i in range(1, 13)}
    for i in range(1, 13):
        sid = f"sub-{i:03d}"
        for name in default_registry().names():
            report = loaded_app.analysis_service.run(sid, name, loaded_app.context)
            stored = loaded_app.repository.get(sid)
            assert stored is not None
            validate_report(report, stored, loaded_app.context)
    assert {i: loaded_app.repository.get(f"sub-{i:03d}") for i in range(1, 13)} == snapshot


def test_corpus_injection_text_never_becomes_score_or_verdict(loaded_app: Application) -> None:
    for name in default_registry().names():
        report = loaded_app.analysis_service.run("sub-010", name, loaded_app.context)
        assert all(f.score is None and f.kind != "processing_error" for f in report.findings)
        assert "максимальн" not in " ".join(f.explanation for f in report.findings).lower()


def test_evidence_lines_always_point_to_existing_source(loaded_app: Application) -> None:
    for i in range(1, 13):
        sid = f"sub-{i:03d}"
        stored = loaded_app.repository.get(sid)
        assert stored is not None
        for name in ("length", "template"):
            for finding in loaded_app.analysis_service.run(sid, name, loaded_app.context).findings:
                for e in finding.evidence:
                    lines = getattr(stored, e.field).splitlines()
                    assert 1 <= e.start_line <= e.end_line <= len(lines)
