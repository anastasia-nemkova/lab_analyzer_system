"""Сервис приёма, репозиторий и неизменяемость модели: приём, дубликат, конфликт, ошибки"""

import copy
import dataclasses

import pytest

from lab_analyzer.errors import CONFLICT, SubmissionError
from lab_analyzer.models import AIDeclaration, Assignment, Evidence, Finding, Submission
from lab_analyzer.repositories import InMemorySubmissionRepository
from lab_analyzer.services import SubmissionService
from tests.cases import RAW_EXAMPLE, changed


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


def test_models_are_frozen(submission: Submission) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        submission.code = "x"
    with pytest.raises(dataclasses.FrozenInstanceError):
        submission.ai_declaration.used = True 


@pytest.mark.parametrize(
    "instance",
    [
        AIDeclaration(False, None, None, True),
        Assignment("a", "", ()),
        Evidence("s", "code", 1, 1),
        Finding("rubric_feedback", None, (), "x"),
    ],
)
def test_models_use_slots_and_have_no_dict(instance: object) -> None:
    assert not hasattr(instance, "__dict__")
    with pytest.raises((AttributeError, TypeError)):
        instance.unexpected = 1


def test_domain_model_has_no_mutable_containers(submission: Submission) -> None:
    for field in dataclasses.fields(submission):
        assert not isinstance(getattr(submission, field.name), (list, dict, set))


def test_repository_get_missing_and_len(submission: Submission) -> None:
    repo = InMemorySubmissionRepository()
    assert repo.get("nope") is None and len(repo) == 0
    repo.add(submission)
    assert repo.get("sub-001") is submission and len(repo) == 1


def test_failed_add_keeps_original_object(submission: Submission) -> None:
    repo = InMemorySubmissionRepository()
    repo.add(submission)
    other = dataclasses.replace(submission, code="changed")
    with pytest.raises(SubmissionError) as caught:
        repo.add(other)
    assert caught.value.code == CONFLICT
    assert repo.get("sub-001") is submission


def test_accept_submission_conflict(submission: Submission) -> None:
    service = SubmissionService(InMemorySubmissionRepository())
    service.accept_submission(submission)
    with pytest.raises(SubmissionError) as caught:
        service.accept_submission(dataclasses.replace(submission, text="другая версия"))
    assert caught.value.code == CONFLICT


def test_service_works_with_any_repository_implementing_protocol(submission: Submission) -> None:
    class DictRepo:
        def __init__(self) -> None:
            self.data: dict[str, Submission] = {}

        def get(self, submission_id: str) -> Submission | None:
            return self.data.get(submission_id)

        def add(self, s: Submission) -> None:
            self.data[s.submission_id] = s

    repo = DictRepo()
    result = SubmissionService(repo).accept_submission(submission)
    assert result.status == "accepted" and "sub-001" in repo.data


def test_duplicate_does_not_touch_repository(submission: Submission) -> None:
    class CountingRepo(InMemorySubmissionRepository):
        adds = 0

        def add(self, s: Submission) -> None:
            type(self).adds += 1
            super().add(s)

    service = SubmissionService(CountingRepo())
    service.accept_submission(submission)
    service.accept_submission(submission)
    assert CountingRepo.adds == 1


def test_accept_submission_matches_accept(submission: Submission) -> None:
    left = SubmissionService(InMemorySubmissionRepository())
    right = SubmissionService(InMemorySubmissionRepository())
    assert left.accept(RAW_EXAMPLE) == right.accept_submission(submission)
