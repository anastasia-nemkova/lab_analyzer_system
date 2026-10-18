"""Общие тестовые данные"""

import copy
from typing import Any

RAW_EXAMPLE: dict[str, Any] = {
    "schema_version": 1,
    "submission_id": "sub-001",
    "student_id": "student-001",
    "assignment_id": "assignment-01",
    "submitted_at": "2026-09-01T10:01:00+03:00",
    "text": "Учебное решение с пояснением алгоритма.",
    "code": (
        "from typing import Iterable\n\n"
        "def solve(values: Iterable[int]) -> int:\n"
        "    return sum(x * x for x in values if x >= 0)\n"
    ),
    "template_id": "template-01",
    "ai_declaration": {
        "used": False,
        "tool": None,
        "purpose": None,
        "verified_by_student": True,
    },
}


def changed(**updates: Any) -> dict[str, Any]:
    result = copy.deepcopy(RAW_EXAMPLE)
    result.update(updates)
    return result


def declaration(**updates: Any) -> dict[str, Any]:
    base = copy.deepcopy(RAW_EXAMPLE["ai_declaration"])
    assert isinstance(base, dict)
    base.update(updates)
    return base


VALIDATION_CASES: list[tuple[str, dict[str, Any], str, str]] = [
    ("version-bool", changed(schema_version=True), "schema_error", "schema_version"),
    ("version-2", changed(schema_version=2), "unsupported_version", "schema_version"),
    ("code-int", changed(code=123), "schema_error", "code"),
    ("naive-time", changed(submitted_at="2026-09-01T10:00:00"), "schema_error", "submitted_at"),
    ("empty-student", changed(student_id="  "), "schema_error", "student_id"),
    ("unknown-field", changed(unknown="value"), "schema_error", "unknown"),
    (
        "typo-field",
        {**{k: v for k, v in RAW_EXAMPLE.items() if k != "student_id"}, "studnet_id": "x"},
        "schema_error",
        "student_id",
    ),
    ("empty-work", changed(text=" ", code="\n"), "schema_error", "text/code"),
    (
        "declaration-incomplete",
        changed(ai_declaration=declaration(used=True)),
        "schema_error",
        "ai_declaration",
    ),
    (
        "declaration-nested-unknown",
        changed(ai_declaration=declaration(note="x")),
        "schema_error",
        "ai_declaration.note",
    ),
    (
        "declaration-missing-field",
        changed(ai_declaration={"used": False, "tool": None, "purpose": None}),
        "schema_error",
        "ai_declaration.verified_by_student",
    ),
    (
        "declaration-false-string",
        changed(ai_declaration=declaration(verified_by_student="false")),
        "schema_error",
        "ai_declaration.verified_by_student",
    ),
    ("declaration-not-object", changed(ai_declaration=[]), "schema_error", "ai_declaration"),
    ("null-required-string", changed(submission_id=None), "schema_error", "submission_id"),
    ("template-blank", changed(template_id=" "), "schema_error", "template_id"),
]
