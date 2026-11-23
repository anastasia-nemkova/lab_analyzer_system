"""
Командный интерфейс для импорта и анализа сдач из JSONL файлов.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from lab_analyzer import __version__
from lab_analyzer.app import build_application
from lab_analyzer.config import DEFAULT_CONFIG, AppConfig, load_config
from lab_analyzer.errors import AnalysisFailure, ConfigError
from lab_analyzer.importer import import_source
from lab_analyzer.reporting import report_to_dict
from lab_analyzer.sources import JSONLSource

EXIT_OK = 0 # полностью успешно
EXIT_ROW_ERRORS = 1 # ошибки отдельных строк либо анализа
EXIT_UNAVAILABLE = 2 # источник или конфигурация недоступны/некорректны

_LOGGER_NAME = "lab_analyzer"
_HANDLER_MARK = "_lab_analyzer_cli"

def _configure_logging(verbose: bool) -> None:
    """
    Настраивает логгер пакета в точке запуска
    """
    logger = logging.getLogger(_LOGGER_NAME)
    for old in logger.handlers[:]:
        if getattr(old, _HANDLER_MARK, False):
            logger.removeHandler(old)

    handler = logging.StreamHandler(sys.stderr)
    setattr(handler, _HANDLER_MARK, True)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))

    logger.addHandler(handler)
    logger.setLevel(logging.INFO if verbose else logging.WARNING)
    logger.propagate = False

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab-analyzer", 
        description="Приём и анализ лабораторных работ из JSONL"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, help="Доступные команды")

    imp = sub.add_parser("import", help="Импортировать файл сдач из JSONL")
    imp.add_argument("path", type=Path, help="Путь к JSONL-файлу")
    imp.add_argument("--config", type=Path, default=None, help="Путь к JSON-файлу конфигурации")
    imp.add_argument("-v", "--verbose", action="store_true", help="Журнал в stderr")
    imp.add_argument("--analyze", action="store_true", help="Запустить анализаторы из конфигурации")

    ana = sub.add_parser("analyze", help="Запустить анализатор для уже принятой сдачи")
    ana.add_argument("--config", type=Path, default=None, help="Путь к JSON-файлу конфигурации")
    ana.add_argument("-v", "--verbose", action="store_true", help="Журнал в stderr")
    ana.add_argument("submission_id", help="ID принятой сдачи")
    ana.add_argument("analyzer_name", help="Имя анализатора (например, length, template)")

    return parser


def _error(code: str, message: str) -> None:
    print(json.dumps({"code": code, "message": message}, ensure_ascii=False), file=sys.stderr)

def _handle_import(args: argparse.Namespace, app: Any, config: AppConfig) -> int:
    """ Обработка команды import"""
    try:
        summary = import_source(JSONLSource(args.path), app.submission_service)
    except (OSError, UnicodeError) as exc:
        _error("source_unavailable", str(exc))
        return EXIT_UNAVAILABLE

    output: dict[str, Any] = summary.to_dict()
    has_errors = bool(summary.errors)

    if args.analyze:
        reports: list[dict[str, Any]] = []
        analysis_errors: list[dict[str, str]] = []
        
        for submission_id in summary.accepted:
            for name in config.analyzers:
                try:
                    report = app.analysis_service.run(submission_id, name, app.context)
                except AnalysisFailure as exc:
                    analysis_errors.append({
                        "submission_id": submission_id, 
                        "analyzer": name, 
                        "message": exc.message
                    })
                else:
                    reports.append(report_to_dict(report))
                    
        output["reports"] = reports
        output["analysis_errors"] = analysis_errors
        has_errors = has_errors or bool(analysis_errors)

    print(json.dumps(output, ensure_ascii=False))
    return EXIT_ROW_ERRORS if has_errors else EXIT_OK
    
def _handle_analyze(args: argparse.Namespace, app: Any) -> int:
    """ Обработка команды analyze"""
    try:
        report = app.analysis_service.run(args.submission_id, args.analyzer_name, app.context)
    except AnalysisFailure as exc:
        _error("analysis_failed", exc.message)
        return EXIT_ROW_ERRORS

    print(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2))
    return EXIT_OK

def cli_main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_logging(args.verbose)

    try:
        config: AppConfig = DEFAULT_CONFIG if args.config is None else load_config(args.config)
        app = build_application(config)
    except ConfigError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False), file=sys.stderr)
        return EXIT_UNAVAILABLE
    except (OSError, UnicodeError) as exc:
        _error("config_unavailable", f"Конфигурация недоступна: {exc}")
        return EXIT_UNAVAILABLE

    if args.command == "import":
        return _handle_import(args, app, config)
    elif args.command == "analyze":
        return _handle_analyze(args, app)
    
    return EXIT_OK

def main() -> None:
    sys.exit(cli_main())

if __name__ == "__main__":
    main()