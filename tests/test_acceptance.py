import copy

import pytest

from lab_analyzer.errors import SubmissionError
from lab_analyzer.repositories import InMemorySubmissionRepository
from lab_analyzer.services import SubmissionService
from tests.cases import changed


def test_accept_then_duplicate_then_conflict(
    service: SubmissionService, repository: InMemorySubmissionRepository, raw_submission
) -> None:
    first = service.accept(raw_submission)
    assert first.status == "accepted"
    original = repository.get("sub-001")

    again = service.accept(copy.deepcopy(raw_submission))
    assert again.status == "duplicate"
    assert again.content_hash == first.content_hash
    assert len(repository) == 1

    with pytest.raises(SubmissionError) as caught:
        service.accept(changed(code="print('другая версия')"))
    assert caught.value.code == "conflict"
    assert caught.value.field == "submission_id"
    assert repository.get("sub-001") == original 
    assert len(repository) == 1


def test_invalid_input_does_not_change_state(
    service: SubmissionService, repository: InMemorySubmissionRepository, raw_submission
) -> None:
    service.accept(raw_submission)
    snapshot = repository.get("sub-001")
    with pytest.raises(SubmissionError) as caught:
        service.accept(changed(submission_id="sub-002", student_id=""))
    assert caught.value.code == "schema_error"
    assert repository.get("sub-002") is None
    assert repository.get("sub-001") == snapshot
    assert len(repository) == 1


def test_new_version_with_new_id_keeps_both(
    service: SubmissionService, repository: InMemorySubmissionRepository, raw_submission
) -> None:
    service.accept(raw_submission)
    new = service.accept(
        changed(submission_id="sub-001-v2", code="def solve(values):\n    return 0\n")
    )
    assert new.status == "accepted"
    assert len(repository) == 2
    first, second = repository.get("sub-001"), repository.get("sub-001-v2")
    assert first is not None and second is not None
    assert first.code != second.code


def test_repository_rejects_overwrite_directly(
    repository: InMemorySubmissionRepository, submission
) -> None:
    repository.add(submission)
    with pytest.raises(SubmissionError) as caught:
        repository.add(submission)
    assert caught.value.code == "conflict"


def test_accept_does_not_mutate_input(service: SubmissionService, raw_submission) -> None:
    before = copy.deepcopy(raw_submission)
    service.accept(raw_submission)
    assert raw_submission == before

def test_batch_processing_continues_on_error(
    service: SubmissionService, repository: InMemorySubmissionRepository, raw_submission
) -> None:
    service.accept(copy.deepcopy(raw_submission))
    assert len(repository) == 1

    batch = [
        changed(submission_id="sub-002", text="Вторая работа"),
        changed(submission_id="sub-003", student_id=""),
        changed(submission_id="sub-004", text="Четвертая работа"),
    ]

    accepted_ids = []
    errors_count = 0

    for raw in batch:
        try:
            res = service.accept(raw)
            if res.status == "accepted":
                accepted_ids.append(res.submission_id)
        except SubmissionError:
            errors_count += 1

    assert errors_count == 1
    assert set(accepted_ids) == {"sub-002", "sub-004"}
    assert len(repository) == 3
