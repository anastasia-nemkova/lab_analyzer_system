"""Конфигурация приложения: строгая валидация, сборка зависимостей, fail-fast"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from lab_analyzer.app import build_application, default_registry
from lab_analyzer.config import DEFAULT_CONFIG, AppConfig, ConfigInput, load_config, parse_config
from lab_analyzer.errors import AnalysisFailure, ConfigError
from lab_analyzer.registry import AnalyzerRegistry
from lab_analyzer.repositories import InMemorySubmissionRepository
from tests.cases import RAW_EXAMPLE

ROOT = Path(__file__).resolve().parent.parent


CONFIG = ROOT / "data" / "config.example.json"


def test_build_with_injected_repository_uses_it() -> None:
    repo = InMemorySubmissionRepository()
    app = build_application(repository=repo)
    app.submission_service.accept(RAW_EXAMPLE)
    assert repo.get("sub-001") is not None and app.repository is repo


def test_build_with_injected_registry_and_config() -> None:
    registry = default_registry()
    config = replace(DEFAULT_CONFIG, analyzers=("missing-explanation",))
    app = build_application(config, registry=registry)
    app.submission_service.accept(RAW_EXAMPLE)
    assert [r.analyzer_id for r in app.analyze_all("sub-001")] == ["missing-explanation"]


def test_build_validates_every_analyzer_not_only_first() -> None:
    config = replace(DEFAULT_CONFIG, analyzers=("length", "template", "ghost"))
    with pytest.raises(ConfigError) as caught:
        build_application(config)
    assert caught.value.field == "analyzers" and "ghost" in caught.value.message


def test_build_with_empty_registry_fails_fast() -> None:
    with pytest.raises(ConfigError):
        build_application(DEFAULT_CONFIG, registry=AnalyzerRegistry())


def test_app_context_follows_config() -> None:
    config = replace(DEFAULT_CONFIG, mode="stub", config_version="9")
    ctx = build_application(config).context
    assert ctx.mode == "stub" and ctx.config_version == "9"


def test_config_example_file_matches_builtins() -> None:
    from lab_analyzer.config import load_config

    cfg = load_config(CONFIG)
    assert isinstance(cfg, AppConfig)
    assert set(cfg.analyzers) <= set(default_registry().names())


def test_config_is_frozen() -> None:
    with pytest.raises(AttributeError):
        DEFAULT_CONFIG.mode = "stub"


def test_config_requirements_become_tuple_and_input_unchanged() -> None:
    raw: dict[str, Any] = {
        "assignment": {"assignment_id": "a", "allowed_template": "", "requirements": ["r"]},
        "analyzers": ["length"],
    }
    cfg = parse_config(raw)
    assert cfg.assignment.requirements == ("r",)
    assert raw["assignment"]["requirements"] == ["r"]


def test_config_model_has_analyzers_field() -> None:
    assert "analyzers" in ConfigInput.model_fields
    assert "analyzer" not in ConfigInput.model_fields


def test_config_with_old_key_is_rejected() -> None:
    with pytest.raises(ConfigError):
        parse_config(
            {
                "assignment": {"assignment_id": "a", "allowed_template": "", "requirements": []},
                "analyzer": ["length"],
            }
        )


def test_error_reprs_are_informative() -> None:
    assert "field = 'x'" in repr(ConfigError("x", "msg"))
    assert repr(ConfigError("x", "msg")).endswith(")")
    assert "message = 'boom'" in repr(AnalysisFailure("boom"))
    assert str(AnalysisFailure("boom")) == "boom"


def test_config_error_to_dict() -> None:
    assert ConfigError("f", "m").to_dict() == {
        "code": "config_invalid", "field": "f", "message": "m",
    }


def _cfg(**updates: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "assignment": {
            "assignment_id": "assignment-01",
            "allowed_template": "x\n",
            "requirements": ["r"],
        },
        "analyzers": ["length"],
    }
    base.update(updates)
    return base


def test_parse_config_ok() -> None:
    cfg = parse_config(_cfg(config_version="7"))
    assert cfg.analyzers == ("length",)
    assert cfg.config_version == "7"
    assert cfg.assignment.requirements == ("r",)


@pytest.mark.parametrize(
    ("raw", "field"),
    [
        (_cfg(analyzers=[]), "analyzers"),
        (_cfg(analyzers=["length", "length"]), "analyzers"),
        (_cfg(analyzers=[" "]), "analyzers"),
        (_cfg(analyzers="length"), "analyzers"),
        (_cfg(mode="turbo"), "mode"),
        (_cfg(config_version=" "), "config_version"),
        (_cfg(unknown=1), "unknown"),
        (_cfg(assignment={"assignment_id": " ", "allowed_template": "", "requirements": []}),
         "assignment.assignment_id"),
        ({"analyzers": ["length"]}, "assignment"),
    ],
)
def test_parse_config_rejects(raw: dict[str, Any], field: str) -> None:
    with pytest.raises(ConfigError) as caught:
        parse_config(raw)
    assert caught.value.field == field


def test_load_config_file(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text('{"analyzers": ["length"], "assignment": '
                    '{"assignment_id": "a", "allowed_template": "", "requirements": []}}',
                    encoding="utf-8")
    assert load_config(path).assignment.assignment_id == "a"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "absent.json")


def test_applications_are_isolated() -> None:
    first, second = build_application(), build_application()
    first.submission_service.accept(RAW_EXAMPLE)
    assert second.repository.get("sub-001") is None


def test_build_application_default_and_end_to_end() -> None:
    app = build_application()
    assert app.submission_service.accept(RAW_EXAMPLE).status == "accepted"
    reports = app.analyze_all("sub-001")
    assert [r.analyzer_id for r in reports] == list(DEFAULT_CONFIG.analyzers)
