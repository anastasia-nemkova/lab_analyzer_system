"""
Тесты хеширования: устойчивость, независимость от порядка ключей, чувствительность к данным
"""

import copy
import json
import subprocess
import sys
from dataclasses import replace
from typing import Any

import pytest

from lab_analyzer.hashing import canonical_json, stable_hash, submission_hash
from lab_analyzer.models import Submission
from lab_analyzer.parsing import parse_submission
from tests.cases import changed


def test_canonical_json_sorted_cyrillic() -> None:
    assert canonical_json({"b": 1, "a": "дом"})  == '{"a":"дом","b":1}'

def test_canonical_json_reject_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"score": float("nan")})

def test_stable_hash_ignores_key_order() -> None:
    assert stable_hash({"a": 1, "b": {"x": 1, "y": 2}}) == stable_hash(
        {"b": {"y": 2, "x": 1}, "a": 1}
    )

def test_stable_hash_is_sha256_hex_and_repeatable() -> None:
    digest = stable_hash({"a": 1})
    assert len(digest) == 64
    assert int(digest, 16) >= 0
    assert digest == stable_hash({"a": 1})

def test_submission_hash_ignores_key_order_of_input(
    raw_submission: dict[str, Any], submission: Submission
) -> None:
    reordered = dict(reversed(list(raw_submission.items())))
    assert submission_hash(parse_submission(reordered)) == submission_hash(submission)


@pytest.mark.parametrize(
    "field, value",
    [
        ("student_id", "student-other"),
        ("text", "Другой текст"),
        ("code", "print(1)\n"),
        ("assignment_id", "assignment-02"),
        ("template_id", None),
    ],
)
def test_submission_hash_changes_with_any_field(
    submission: Submission, field: str, value: object
) -> None:
    assert submission_hash(replace(submission, **{field: value})) != submission_hash(submission)


def test_submission_hash_covers_nested_declaration(submission: Submission) -> None:
    other = replace(
        submission, ai_declaration=replace(submission.ai_declaration, verified_by_student=False)
    )
    assert submission_hash(other) != submission_hash(submission)


def test_trailing_whitespace_in_code_changes_hash(submission: Submission) -> None:
    assert submission_hash(replace(submission, code=submission.code + " ")) != submission_hash(
        submission
    )


def test_same_instant_in_other_representation_changes_hash(submission: Submission) -> None:
    other = parse_submission(changed(submitted_at="2026-09-01T07:01:00Z"))
    assert submission_hash(other) != submission_hash(submission)


def test_hash_does_not_mutate_submission(submission: Submission) -> None:
    before = copy.deepcopy(submission)
    submission_hash(submission)
    assert submission == before


def test_hash_is_stable_across_processes(submission: Submission) -> None:
    code = (
        "import json, sys\n"
        "from lab_analyzer.hashing import stable_hash\n"
        "print(stable_hash(json.loads(sys.argv[1])))\n"
    )
    payload = json.dumps({"text": "дом", "n": 1})
    outputs = {
        subprocess.run(
            [sys.executable, "-c", code, payload],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": seed, "PYTHONPATH": "src"},
        ).stdout.strip()
        for seed in ("1", "2", "3")
    }
    assert outputs == {stable_hash({"text": "дом", "n": 1})}
