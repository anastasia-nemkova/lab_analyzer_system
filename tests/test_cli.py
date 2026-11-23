"""CLI: потоки stdout/stderr, коды завершения и сквозной сценарий на встроенном корпусе"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from lab_analyzer import __version__
from lab_analyzer.app import build_application
from lab_analyzer.cli import cli_main
from lab_analyzer.importer import import_source
from lab_analyzer.reporting import validate_report
from lab_analyzer.sources import InMemorySource, JSONLSource
from tests.cases import RAW_EXAMPLE, changed

ROOT = Path(__file__).resolve().parent.parent


CORPUS = ROOT / "data" / "submissions.jsonl"


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        cli_main(["--version"])
    assert caught.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_cli_import_requires_path() -> None:
    with pytest.raises(SystemExit) as caught:
        cli_main(["import"])
    assert caught.value.code == 2


def test_cli_invalid_utf8_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "c.json"
    bad.write_bytes(b"\xff\xfe")
    assert cli_main(["import", str(CORPUS), "--config", str(bad)]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "config_unavailable"


def test_cli_broken_config_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "c.json"
    bad.write_text("{oops", encoding="utf-8")
    assert cli_main(["import", str(CORPUS), "--config", str(bad)]) == 2
    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "config_invalid" and err["field"] == "json"


def test_cli_does_not_touch_root_logger(capsys: pytest.CaptureFixture[str]) -> None:
    before = list(logging.getLogger().handlers)
    cli_main(["import", str(CORPUS), "-v"])
    assert logging.getLogger().handlers == before


def test_cli_repeated_calls_do_not_stack_handlers(capsys: pytest.CaptureFixture[str]) -> None:
    for _ in range(3):
        cli_main(["import", str(CORPUS)])
    marked = [h for h in logging.getLogger("lab_analyzer").handlers
              if getattr(h, "_lab_analyzer_cli", False)]
    assert len(marked) == 1

@pytest.fixture
def mixed_path(tmp_path: Path) -> Path:
    lines = [
        json.dumps(RAW_EXAMPLE),
        "{broken",
        json.dumps(RAW_EXAMPLE),
        json.dumps(changed(text="Другое содержимое с тем же ID")),
        json.dumps(changed(submission_id="bad-record", student_id="")),
        json.dumps(changed(submission_id="sub-002")),
    ]
    path = tmp_path / "mixed.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_exit_code_1_and_single_json_on_stdout(
    mixed_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli_main(["import", str(mixed_path)])
    captured = capsys.readouterr()
    assert code == 1
    data = json.loads(captured.out)
    assert data["accepted"] == ["sub-001", "sub-002"]
    assert data["duplicate"] == ["sub-001"]
    assert [e["line_no"] for e in data["errors"]] == [2, 4, 5]
    assert "reports" not in data


def test_exit_code_0_on_clean_corpus(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["import", str(CORPUS)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["accepted"]) == 12 and data["errors"] == []


def test_exit_code_2_when_source_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli_main(["import", str(tmp_path / "absent.jsonl")])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert json.loads(captured.err)["code"] == "source_unavailable"


def test_exit_code_2_on_invalid_utf8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_bytes(b"\xff\xfe\n")
    assert cli_main(["import", str(path)]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "source_unavailable"


def test_exit_code_2_on_invalid_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "c.json"
    config.write_text('{"analyzers": ["ghost"], "assignment": '
                      '{"assignment_id": "a", "allowed_template": "", "requirements": []}}',
                      encoding="utf-8")
    assert cli_main(["import", str(CORPUS), "--config", str(config)]) == 2
    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "config_invalid" and "ghost" in err["message"]


def test_exit_code_2_on_missing_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli_main(["import", str(CORPUS), "--config", str(tmp_path / "none.json")]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "config_unavailable"


def test_analyze_flag_produces_reports(capsys: pytest.CaptureFixture[str]) -> None:
    config = ROOT / "data" / "config.example.json"
    assert cli_main(["import", str(CORPUS), "--analyze", "--config", str(config)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["reports"]) == 12 * 4
    assert data["analysis_errors"] == []
    assert {r["analyzer_id"] for r in data["reports"]} == {
        "length", "template", "declaration", "missing-explanation"
    }


def test_analysis_errors_set_exit_code_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "other.jsonl"
    path.write_text(json.dumps(changed(assignment_id="assignment-99")) + "\n", encoding="utf-8")
    assert cli_main(["import", str(path), "--analyze"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["errors"] == [] and len(data["analysis_errors"]) == 3


def test_verbose_logs_go_to_stderr_without_source_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli_main(["import", str(CORPUS), "-v"])
    captured = capsys.readouterr()
    assert "INFO lab_analyzer.importer" in captured.err
    assert "def solve" not in captured.err
    json.loads(captured.out)


def test_no_subcommand_is_usage_error() -> None:
    with pytest.raises(SystemExit) as caught:
        cli_main([])
    assert caught.value.code == 2


def test_module_entry_point_runs_in_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "lab_analyzer", "import", str(CORPUS)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert len(json.loads(result.stdout)["accepted"]) == 12


def test_end_to_end() -> None:
    app = build_application()
    first = import_source(JSONLSource(CORPUS), app.submission_service)
    second = import_source(JSONLSource(CORPUS), app.submission_service)
    assert len(first.accepted) == 12 and not first.errors
    assert len(second.duplicate) == 12 and not second.accepted and not second.errors

    count = 0
    for submission_id in first.accepted:
        original = app.repository.get(submission_id)
        assert original is not None
        for name in ("length", "template"):
            report = app.analysis_service.run(submission_id, name, app.context)
            validate_report(report, original, app.context)
            assert app.repository.get(submission_id) == original
            count += 1
    assert count == 24


def test_both_sources_give_same_acceptance() -> None:
    values = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines()]
    left, right = build_application(), build_application()
    a = import_source(InMemorySource(values), left.submission_service)
    b = import_source(JSONLSource(CORPUS), right.submission_service)
    assert a.accepted == b.accepted and a.errors == b.errors
    

def test_cli_analyze_unknown_submission(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli_main(["analyze", "no-such-id", "length"])
    captured = capsys.readouterr()
    assert code == 1 and captured.out == ""
    assert json.loads(captured.err)["code"] == "analysis_failed"

    
