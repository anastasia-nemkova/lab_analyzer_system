"""
Источники данных для импорта сдач
"""

import copy
from collections.abc import Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TextIO

from lab_analyzer.errors import SubmissionError
from lab_analyzer.parsing import decode_json


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """
    Одна запись из источника данных
    """
    line_no: int
    raw: dict[str, Any] | None = None
    error: SubmissionError | None = None

class SubmissionSource(Protocol):
    """
    Структурный контракт источника
    """
    def open(self) -> AbstractContextManager[Iterator[SourceRecord]]:
        ...

def iter_jsonl(lines: Iterable[str]) -> Iterator[SourceRecord]:
    """
    Разбирает JSONL построчно
    """
    for number, line in enumerate(lines, start=1):
        try:
            raw = decode_json(line)
        except SubmissionError as exc:
            yield SourceRecord(number, error=exc)
        else:
            yield SourceRecord(number, raw=raw)

class InMemorySource:
    """
    Источник из списка словарей в памяти
    """
    def __init__(self, values: list[dict[str, Any]]) -> None:
        self._values = copy.deepcopy(values)

    @contextmanager
    def open(self) -> Iterator[Iterator[SourceRecord]]:
        def records() -> Iterator[SourceRecord]:
            for number, raw in enumerate(self._values, start=1):
                yield SourceRecord(line_no=number, raw=copy.deepcopy(raw))

        yield records()

class JSONLSource:
    """
    Источник из JSONL файла
    """
    def __init__(self, path: Path) -> None:
        self.path = path
        self.last_closed: bool | None = None

    @contextmanager
    def open(self) -> Iterator[Iterator[SourceRecord]]:
        handle = self.path.open("r", encoding="utf-8")
        try:
            yield iter_jsonl(handle)
        finally: 
            handle.close()
            self.last_closed = handle.closed

class StreamSource:
    """
    JSONL из готового текстового потока (io.StringIO).
    """
    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    @contextmanager
    def open(self) -> Iterator[Iterator[SourceRecord]]:
        yield iter_jsonl(self._stream)