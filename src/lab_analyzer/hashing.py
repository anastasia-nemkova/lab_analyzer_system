"""
Вычисление устойчивого SHA-256 хеша для доменных моделей
"""
import hashlib
import json
from dataclasses import asdict
from typing import Any

from lab_analyzer.models import Submission


def canonical_json(value: Any) -> str:
    """Сериализует объект в канонический JSON"""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

def stable_hash(value: Any) -> str:
    """Вычисляет SHA-256 хеш от канонического JSON представления объекта"""
    canonical_bytes = canonical_json(value).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()

def submission_hash(submission: Submission) -> str:
    """Вычисляет хеш конкретной доменной модели Submission"""
    return stable_hash(asdict(submission))