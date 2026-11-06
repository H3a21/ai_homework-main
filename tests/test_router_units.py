"""Unit tests for API router logic with deterministic fake sessions."""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import (
    Assignment,
    Class,
    ClassMember,
    GradingResult,
    KnowledgePoint,
    KnowledgeRelation,
    Question,
    StudentKnowledgeMastery,
    Subject,
    Submission,
    SubmissionImage,
    User,
)
from app.routers import assignments, classes, knowledge, reports, submissions, students


class FakeScalars:
    def __init__(self, values):
        self.values = list(values)

    def all(self):
        return self.values


class FakeResult:
    def __init__(self, scalar=None, scalars=None, rows=None):
        self.scalar = scalar
        self.scalar_values = scalars or []
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return FakeScalars(self.scalar_values)

    def all(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class FakeDB:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.added = []
        self.commits = 0

    async def execute(self, statement):
        if not self.results:
            raise AssertionError("Unexpected database query in unit test")
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        if value.id is None:
            value.id = 99


def test_class_list_detail_create_and_add_student():
    teacher = SimpleNamespace(id=5, role="teacher")
    cls = Class(id=1, name="Class A", grade="6", invite_code="ABC12345")
    member_user = User(
        id=7,
        username="student_a",
        password_hash="x",
        display_name="Student A",
        role="student",
    )

    async def run():
        listed = await classes.list_classes(
            FakeDB([FakeResult(scalars=[cls])]), teacher
        )
        assert listed[0]["name"] == "Class A"

        detail = await classes.get_class(
            1,
            FakeDB([
                FakeResult(scalar=cls),
                FakeResult(scalar=ClassMember(id=1)),
                FakeResult(rows=[(member_user, "student")]),
            ]),
            teacher,
        )
        assert detail["members"][0]["class_role"] == "student"

        create_db = FakeDB()
        created = await classes.create_class(
            classes.CreateClassRequest(name="Class B", grade="7"),
            create_db,
            teacher,
        )
        assert created["id"] == 99
        assert create_db.commits == 2

        add_db = FakeDB([
            FakeResult(scalar=cls),
            FakeResult(scalar=ClassMember(id=1)),
            FakeResult(scalar=member_user),
            FakeResult(scalar=None),
        ])
        result = await classes.add_student(
            1, classes.AddStudentRequest(student_id=7), add_db, teacher
        )
        assert "message" in result

    asyncio.run(run())


def test_student_list_serializes_records():
    async def run():
        records = [
            User(id=8, username="student", password_hash="x", display_name="Student", role="student")
        ]
        result = await students.list_students(
            FakeDB([FakeResult(scalars=records)]),
            SimpleNamespace(id=5, role="teacher"),
        )
        assert result == [{"id": 8, "username": "student", "display_name": "Student"}]

    asyncio.run(run())


def test_class_and_student_errors_are_explicit():
    async def run():
        with pytest.raises(HTTPException) as missing_class:
            await classes.get_class(1, FakeDB([FakeResult()]), SimpleNamespace(id=1, role="student"))
        assert missing_class.value.status_code == 404

        with pytest.raises(HTTPException) as missing_student:
            await classes.add_student(
                1,
                classes.AddStudentRequest(student_id=2),
                FakeDB([
                    FakeResult(scalar=Class(id=1)),
                    FakeResult(scalar=ClassMember(id=1)),
                    FakeResult(),
                ]),
                SimpleNamespace(id=1, role="teacher"),
            )
        assert missing_student.value.status_code == 404

        with pytest.raises(HTTPException) as duplicate:
            await classes.add_student(
                1,
                classes.AddStudentRequest(student_id=2),
                FakeDB([
                    FakeResult(scalar=Class(id=1)),
                    FakeResult(scalar=ClassMember(id=1)),
                    FakeResult(scalar=User(id=2, role="student")),
                    FakeResult(scalar=ClassMember(id=3)),
                ]),
                SimpleNamespace(id=1, role="teacher"),
            )
        assert duplicate.value.status_code == 409

    asyncio.run(run())


def test_assignment_list_detail_and_create():
    teacher = SimpleNamespace(id=5, role="teacher")
    created_at = datetime(2026, 1, 1)
    assignment = Assignment(
        id=2, title="Fractions", class_id=1, subject_id=1, teacher_id=5, created_at=created_at
    )
    cls = Class(id=1, name="Class A", grade="6", invite_code="ABC")
    subject = Subject(id=1, name="math")
    question = Question(
        id=3, assignment_id=2, question_number=1, content="2+2", answer="4", max_score=10,
        difficulty=0, discrimination=1,
    )

    async def run():
        listed = await assignments.list_assignments(
            None,
            FakeDB([
                FakeResult(scalars=[assignment]),
                FakeResult(scalar=cls),
                FakeResult(scalar=subject),
                FakeResult(scalars=[question]),
            ]),
            teacher,
        )
        assert listed[0]["question_count"] == 1

        detail = await assignments.get_assignment(
            2,
            FakeDB([
                FakeResult(scalar=assignment),
                FakeResult(scalar=ClassMember(id=1)),
                FakeResult(scalar=cls),
                FakeResult(scalar=subject),
                FakeResult(scalars=[question]),
            ]),
            teacher,
        )
        assert detail["questions"][0]["answer"] == "4"

        db = FakeDB([
            FakeResult(scalar=cls),
            FakeResult(scalar=ClassMember(id=1)),
            FakeResult(scalar=subject),
        ])
        created = await assignments.create_assignment(
            assignments.CreateAssignmentRequest(
                title="New", class_id=1, subject_id=1,
                questions=[{"question_number": 1, "content": "x", "difficulty": 9, "discrimination": 0}],
            ),
            db,
            teacher,
        )
        assert created["id"] == 99
        assert db.added[-1].difficulty == 3.0
        assert db.added[-1].discrimination == 0.1

    asyncio.run(run())


def test_object_level_permissions_and_student_answer_redaction():
    teacher = SimpleNamespace(id=5, role="teacher")
    student = SimpleNamespace(id=8, role="student")
    other_student = SimpleNamespace(id=9, role="student")
    cls = Class(id=1, name="Class A", grade="6", invite_code="ABC")
    subject = Subject(id=1, name="math")
    assignment = Assignment(
        id=2, title="Homework", class_id=1, subject_id=1, teacher_id=5
    )
    question = Question(
        id=3,
        assignment_id=2,
        question_number=1,
        content="2+2",
        answer="4",
        max_score=10,
        difficulty=0,
        discrimination=1,
    )
    submission = Submission(
        id=4, assignment_id=2, student_id=8, status="pending"
    )

    async def run():
        student_detail = await assignments.get_assignment(
            2,
            FakeDB([
                FakeResult(scalar=assignment),
                FakeResult(scalar=ClassMember(id=1)),
                FakeResult(scalar=cls),
                FakeResult(scalar=subject),
                FakeResult(scalars=[question]),
            ]),
            student,
        )
        assert "answer" not in student_detail["questions"][0]

        with pytest.raises(HTTPException) as class_forbidden:
            await classes.get_class(
                1, FakeDB([FakeResult(scalar=cls), FakeResult()]), student
            )
        assert class_forbidden.value.status_code == 403

        with pytest.raises(HTTPException) as add_forbidden:
            await classes.add_student(
                1,
                classes.AddStudentRequest(student_id=8),
                FakeDB([FakeResult(scalar=cls), FakeResult()]),
                teacher,
            )
        assert add_forbidden.value.status_code == 403

        with pytest.raises(HTTPException) as assignment_forbidden:
            await assignments.get_assignment(
                2,
                FakeDB([FakeResult(scalar=assignment), FakeResult()]),
                other_student,
            )
        assert assignment_forbidden.value.status_code == 403

        with pytest.raises(HTTPException) as create_assignment_forbidden:
            await assignments.create_assignment(
                assignments.CreateAssignmentRequest(
                    title="Blocked", class_id=1, subject_id=1
                ),
                FakeDB([FakeResult(scalar=cls), FakeResult()]),
                teacher,
            )
        assert create_assignment_forbidden.value.status_code == 403

        with pytest.raises(HTTPException) as submit_forbidden:
            await submissions.create_submission(
                submissions.CreateSubmissionRequest(assignment_id=2),
                FakeDB([FakeResult(scalar=assignment), FakeResult()]),
                other_student,
            )
        assert submit_forbidden.value.status_code == 403

        with pytest.raises(HTTPException) as submission_forbidden:
            await submissions.get_submission(
                4,
                FakeDB([
                    FakeResult(scalar=submission),
                    FakeResult(scalar=assignment),
                ]),
                other_student,
            )
        assert submission_forbidden.value.status_code == 403

        with pytest.raises(HTTPException) as grade_forbidden:
            await submissions.trigger_grade(
                4,
                FakeDB([
                    FakeResult(scalar=submission),
                    FakeResult(scalar=assignment),
                    FakeResult(),
                ]),
                teacher,
            )
        assert grade_forbidden.value.status_code == 403

        with pytest.raises(HTTPException) as teacher_read_forbidden:
            await submissions.get_submission(
                4,
                FakeDB([
                    FakeResult(scalar=submission),
                    FakeResult(scalar=assignment),
                    FakeResult(),
                ]),
                teacher,
            )
        assert teacher_read_forbidden.value.status_code == 403

        with pytest.raises(HTTPException) as mastery_forbidden:
            await knowledge.get_student_mastery(
                8, None, FakeDB([FakeResult()]), teacher
            )
        assert mastery_forbidden.value.status_code == 403

    asyncio.run(run())


def test_submission_list_detail_create_and_grade_trigger(monkeypatch):
    student = SimpleNamespace(id=8, role="student", display_name="Student")
    teacher = SimpleNamespace(id=5, role="teacher")
    assignment = Assignment(id=2, title="Homework", class_id=1, subject_id=1, teacher_id=5)
    submission = Submission(id=4, assignment_id=2, student_id=8, status="pending", total_score=8)
    image = SubmissionImage(id=6, submission_id=4, image_path="answer.png", page_number=1)
    question = Question(id=3, assignment_id=2, question_number=1, content="2+2", max_score=10)
    result = GradingResult(id=7, submission_id=4, question_id=3, score=8, feedback="Good")
    user_record = User(id=8, username="student", password_hash="x", display_name="Student", role="student")
    uploaded_path = f"submissions/8/{'a' * 32}.png"

    async def run():
        listed = await submissions.list_submissions(
            None, None,
            FakeDB([
                FakeResult(scalars=[submission]), FakeResult(scalar=assignment),
                FakeResult(scalar=user_record), FakeResult(scalars=[image]), FakeResult(scalars=[result]),
            ]),
            teacher,
        )
        assert listed[0]["graded_count"] == 1

        detail = await submissions.get_submission(
            4,
            FakeDB([
                FakeResult(scalar=submission), FakeResult(scalar=assignment),
                FakeResult(scalar=user_record), FakeResult(scalars=[image]),
                FakeResult(scalars=[question]), FakeResult(scalars=[result]),
            ]),
            student,
        )
        assert detail["questions"][0]["score"] == 8.0

        monkeypatch.setattr(
            submissions,
            "read_object",
            lambda path: asyncio.sleep(
                0,
                result=SimpleNamespace(
                    content=b"image-bytes", content_type="image/png"
                ),
            ),
        )
        image_response = await submissions.get_submission_image(
            4,
            6,
            FakeDB([
                FakeResult(scalar=submission),
                FakeResult(scalar=assignment),
                FakeResult(scalar=image),
            ]),
            student,
        )
        assert image_response.body == b"image-bytes"

        monkeypatch.setattr(submissions, "enqueue_grade_submission", lambda value: "task-4")
        monkeypatch.setattr(
            submissions,
            "object_exists",
            lambda path: asyncio.sleep(0, result=True),
        )
        create_db = FakeDB([
            FakeResult(scalar=assignment),
            FakeResult(scalar=ClassMember(id=1)),
            FakeResult(scalar=None),
        ])
        created = await submissions.create_submission(
            submissions.CreateSubmissionRequest(
                assignment_id=2, image_paths=[uploaded_path]
            ),
            create_db,
            student,
        )
        assert created["task_id"] == "task-4"
        assert created["status"] == "grading"

        pending = Submission(id=4, assignment_id=2, student_id=8, status="pending")
        triggered = await submissions.trigger_grade(
            4,
            FakeDB([
                FakeResult(scalar=pending),
                FakeResult(scalar=assignment),
                FakeResult(scalar=ClassMember(id=1)),
            ]),
            teacher,
        )
        assert triggered["task_id"] == "task-4"

    asyncio.run(run())


def test_submission_errors_cover_missing_duplicate_and_conflicting_states(monkeypatch):
    student = SimpleNamespace(id=8, role="student")
    teacher = SimpleNamespace(id=5, role="teacher")
    uploaded_path = f"submissions/8/{'a' * 32}.png"

    async def run():
        with pytest.raises(HTTPException) as missing:
            await submissions.create_submission(
                submissions.CreateSubmissionRequest(assignment_id=2),
                FakeDB([FakeResult()]), student,
            )
        assert missing.value.status_code == 404

        with pytest.raises(HTTPException) as duplicate:
            monkeypatch.setattr(
                submissions,
                "object_exists",
                lambda path: asyncio.sleep(0, result=True),
            )
            await submissions.create_submission(
                submissions.CreateSubmissionRequest(
                    assignment_id=2, image_paths=[uploaded_path]
                ),
                FakeDB([
                    FakeResult(scalar=Assignment(id=2, class_id=1)),
                    FakeResult(scalar=ClassMember(id=1)),
                    FakeResult(scalar=Submission(id=3)),
                ]),
                student,
            )
        assert duplicate.value.status_code == 409

        for status in ("completed", "grading"):
            with pytest.raises(HTTPException) as conflict:
                    await submissions.trigger_grade(
                        4,
                        FakeDB([
                            FakeResult(
                                scalar=Submission(
                                    id=4,
                                    assignment_id=2,
                                    student_id=8,
                                    status=status,
                                )
                            ),
                            FakeResult(scalar=Assignment(id=2, class_id=1)),
                            FakeResult(scalar=ClassMember(id=1)),
                        ]),
                        teacher,
                )
            assert conflict.value.status_code == 409

    asyncio.run(run())


def test_report_permissions_and_cache_paths(monkeypatch):
    student = SimpleNamespace(id=8, role="student")
    teacher = SimpleNamespace(id=5, role="teacher")
    report = {"overview": {"average_mastery": 0.8}}

    async def run():
        monkeypatch.setattr(reports, "get_report", lambda key: asyncio.sleep(0, result=None))
        monkeypatch.setattr(reports, "set_report", lambda key, value: asyncio.sleep(0, result=True))
        monkeypatch.setattr(reports, "load_student_report", lambda *args: asyncio.sleep(0, result=report))
        fresh = await reports.get_student_report(8, None, FakeDB(), student)
        assert fresh["cache"]["hit"] is False

        monkeypatch.setattr(reports, "get_report", lambda key: asyncio.sleep(0, result=report))
        cached = await reports.get_student_report(8, None, FakeDB(), student)
        assert cached["cache"]["hit"] is True

        with pytest.raises(HTTPException) as forbidden:
            await reports.get_student_report(9, None, FakeDB(), student)
        assert forbidden.value.status_code == 403

        monkeypatch.setattr(reports, "_teacher_can_view_class", lambda *args: asyncio.sleep(0, result=True))
        monkeypatch.setattr(reports, "load_class_report", lambda *args: asyncio.sleep(0, result=report))
        class_report = await reports.get_class_report(1, None, FakeDB(), teacher)
        assert class_report["cache"]["hit"] is True

    asyncio.run(run())


def test_knowledge_graph_mastery_and_creation_paths():
    teacher = SimpleNamespace(id=5, role="teacher")
    student = User(id=8, username="s", password_hash="x", display_name="Student", role="student")
    point_a = KnowledgePoint(id=1, subject_id=1, name="Fractions")
    point_b = KnowledgePoint(id=2, subject_id=1, name="Ratios")
    relation = KnowledgeRelation(id=3, prerequisite_id=1, target_id=2, relation_type="prerequisite", strength=0.8)
    subject = Subject(id=1, name="math")
    mastery = StudentKnowledgeMastery(
        id=4, student_id=8, knowledge_point_id=1, mastery_level=0.5,
        ability_theta=0.1, attempt_count=2, success_sum=1.0,
    )

    async def run():
        graph = await knowledge.get_knowledge_graph(
            1,
            FakeDB([FakeResult(scalars=[point_a, point_b]), FakeResult(scalars=[relation])]),
            teacher,
        )
        assert len(graph["points"]) == 2
        assert graph["relations"][0]["strength"] == 0.8

        point_db = FakeDB([FakeResult(scalar=subject), FakeResult(scalar=None)])
        created = await knowledge.create_knowledge_point(
            knowledge.CreateKnowledgePointRequest(subject_id=1, name="  Algebra  "), point_db, teacher
        )
        assert created["name"] == "Algebra"

        relation_db = FakeDB([FakeResult(scalars=[point_a, point_b]), FakeResult(scalar=None)])
        created_relation = await knowledge.create_knowledge_relation(
            knowledge.CreateKnowledgeRelationRequest(prerequisite_id=1, target_id=2, strength=0.7),
            relation_db,
            teacher,
        )
        assert created_relation["strength"] == 0.7

        mastery_result = await knowledge.get_student_mastery(
            8,
            1,
            FakeDB([FakeResult(scalar=student), FakeResult(rows=[(mastery, point_a, subject)])]),
            student,
        )
        assert mastery_result["items"][0]["average_score_ratio"] == 0.5

    asyncio.run(run())
