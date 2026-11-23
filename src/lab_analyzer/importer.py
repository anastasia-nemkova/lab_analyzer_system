"""
Импорт из источника с частичным успехом.
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from lab_analyzer.errors import SubmissionError
from lab_analyzer.services import SubmissionService
from lab_analyzer.sources import SubmissionSource

logger = logging.getLogger(__name__)

@dataclass
class ImportSummary:
    """
    Результат импорта сдач из источника.
    
    Содержит списки ID принятых, дублирующихся и ошибочных записей.
    Ошибки включают номер строки, код, поле и сообщение.
    """
    accepted: list[str] = field(default_factory=list)
    duplicate: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def import_source(source: SubmissionSource, service: SubmissionService) -> ImportSummary:
    """
    Читает источник, принимает каждую запись и собирает итог
    """
    summary = ImportSummary()

    with source.open() as records:
        for record in records:
            if record.error is not None:
                error = record.error
            else:
                assert record.raw is not None
                try:
                    result = service.accept(record.raw)
                except SubmissionError as exc:
                    error = exc
                else:
                    if result.status == "accepted":
                        summary.accepted.append(result.submission_id)
                    else:
                        summary.duplicate.append(result.submission_id)
                    logger.info(
                        "line=%d submission_id=%s result=%s",
                        record.line_no,
                        result.submission_id,
                        result.status,
                    )
                    continue
                
            summary.errors.append(
                {"line_no": record.line_no, **error.to_dict()}
            )

            logger.warning(
                "line=%d code=%s field=%s", record.line_no, error.code, error.field
            )

    return summary