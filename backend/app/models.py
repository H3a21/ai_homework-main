from sqlalchemy import (
    BigInteger, Column, Integer, String, ForeignKey, Text, Enum, Date, DateTime,
    DECIMAL, Index, JSON, UniqueConstraint, func,
)

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(Enum("teacher", "student"), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    grade = Column(String(50))
    invite_code = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class ClassMember(Base):
    __tablename__ = "class_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum("head_teacher", "teacher", "student"), nullable=False, default="student")
    joined_at = Column(DateTime, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("class_id", "user_id", name="uk_class_member"),
    )


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prerequisite_id = Column(
        Integer, ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )
    target_id = Column(
        Integer, ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )
    relation_type = Column(String(30), nullable=False, default="prerequisite")
    strength = Column(DECIMAL(3, 2), nullable=False, default=1.00)

    __table_args__ = (
        UniqueConstraint(
            "prerequisite_id",
            "target_id",
            "relation_type",
            name="uk_knowledge_relation",
        ),
    )


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=True)
    answer = Column(Text, nullable=True, comment="标准答案")
    max_score = Column(DECIMAL(5, 1), nullable=False, default=0)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    difficulty = Column(DECIMAL(4, 2), nullable=False, default=0.00)
    discrimination = Column(DECIMAL(4, 2), nullable=False, default=1.00)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum("pending", "grading", "completed"), default="pending")
    total_score = Column(DECIMAL(6, 1), nullable=True)
    comment = Column(Text, nullable=True)
    submitted_at = Column(DateTime, server_default=func.current_timestamp())
    graded_at = Column(DateTime, nullable=True)


class SubmissionImage(Base):
    __tablename__ = "submission_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    image_path = Column(String(500), nullable=False)
    page_number = Column(Integer, nullable=False, default=1)
    recognized_text = Column(Text, nullable=True)


class GradingResult(Base):
    __tablename__ = "grading_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    score = Column(DECIMAL(5, 1), nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())


class GradingBatch(Base):
    __tablename__ = "grading_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_submissions = Column(Integer, nullable=False, default=0)
    completed_submissions = Column(Integer, nullable=False, default=0)
    failed_submissions = Column(Integer, nullable=False, default=0)
    status = Column(
        Enum("pending", "grading", "completed", "failed"),
        nullable=False,
        default="pending",
    )
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_grading_batch_assignment", "assignment_id", "created_at"),
        Index("idx_grading_batch_teacher", "teacher_id", "created_at"),
    )


class GradingBatchItem(Base):
    __tablename__ = "grading_batch_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(
        Integer,
        ForeignKey("grading_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    submission_id = Column(
        Integer,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id = Column(String(100), nullable=True)
    status = Column(
        Enum("queued", "grading", "completed", "failed"),
        nullable=False,
        default="queued",
    )
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("batch_id", "submission_id", name="uk_grading_batch_item"),
        Index("idx_grading_batch_item_batch", "batch_id", "status"),
        Index("idx_grading_batch_item_submission", "submission_id"),
    )


class GradingAttempt(Base):
    __tablename__ = "grading_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(
        Integer,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number = Column(Integer, nullable=False)
    status = Column(
        Enum("started", "completed", "failed", "skipped"),
        nullable=False,
        default="started",
    )
    total_score = Column(DECIMAL(6, 1), nullable=True)
    raw_ocr_result = Column(JSON, nullable=True)
    result_snapshot = Column(JSON, nullable=True)
    grader_version = Column(String(50), nullable=False, default="1.0.0")
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime, server_default=func.current_timestamp())
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "attempt_number",
            name="uk_submission_attempt",
        ),
        Index("idx_grading_attempt_submission", "submission_id", "started_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(36), nullable=False)
    timestamp = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    outcome = Column(String(20), nullable=False)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=False)

    __table_args__ = (
        Index("idx_audit_time", "timestamp"),
        Index("idx_audit_user", "user_id", "timestamp"),
        Index("idx_audit_resource", "resource_type", "resource_id", "timestamp"),
    )


class StudentKnowledgeMastery(Base):
    __tablename__ = "student_knowledge_mastery"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=False)
    mastery_level = Column(DECIMAL(3, 2), default=0.00)
    ability_theta = Column(DECIMAL(5, 3), nullable=False, default=0.000)
    attempt_count = Column(Integer, nullable=False, default=0)
    success_sum = Column(DECIMAL(8, 3), nullable=False, default=0.000)
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        UniqueConstraint("student_id", "knowledge_point_id", name="uk_student_kp"),
    )
