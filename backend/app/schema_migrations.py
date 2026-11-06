"""Small idempotent schema upgrades for deployments without Alembic."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database import engine


async def _column_names(connection: AsyncConnection, table_name: str) -> set[str]:
    result = await connection.execute(
        text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name"
        ),
        {"table_name": table_name},
    )
    return set(result.scalars())


async def ensure_profile_schema() -> None:
    """Add application tables and columns while preserving an existing database."""
    async with engine.begin() as connection:
        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS grading_attempts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                submission_id INT NOT NULL,
                attempt_number INT NOT NULL,
                status ENUM('started', 'completed', 'failed', 'skipped')
                    NOT NULL DEFAULT 'started',
                total_score DECIMAL(6,1),
                raw_ocr_result JSON,
                result_snapshot JSON,
                grader_version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
                error_message TEXT,
                duration_ms INT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                CONSTRAINT fk_grading_attempt_submission
                    FOREIGN KEY (submission_id) REFERENCES submissions(id)
                    ON DELETE CASCADE,
                UNIQUE KEY uk_submission_attempt
                    (submission_id, attempt_number),
                INDEX idx_grading_attempt_submission
                    (submission_id, started_at)
            )
        """))

        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS grading_batches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                assignment_id INT NOT NULL,
                teacher_id INT NOT NULL,
                total_submissions INT NOT NULL DEFAULT 0,
                completed_submissions INT NOT NULL DEFAULT 0,
                failed_submissions INT NOT NULL DEFAULT 0,
                status ENUM('pending', 'grading', 'completed', 'failed')
                    NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                CONSTRAINT fk_grading_batch_assignment
                    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
                CONSTRAINT fk_grading_batch_teacher
                    FOREIGN KEY (teacher_id) REFERENCES users(id),
                INDEX idx_grading_batch_assignment (assignment_id, created_at),
                INDEX idx_grading_batch_teacher (teacher_id, created_at)
            )
        """))

        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS grading_batch_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                batch_id INT NOT NULL,
                submission_id INT NOT NULL,
                task_id VARCHAR(100),
                status ENUM('queued', 'grading', 'completed', 'failed')
                    NOT NULL DEFAULT 'queued',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                CONSTRAINT fk_grading_batch_item_batch
                    FOREIGN KEY (batch_id) REFERENCES grading_batches(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_grading_batch_item_submission
                    FOREIGN KEY (submission_id) REFERENCES submissions(id)
                    ON DELETE CASCADE,
                UNIQUE KEY uk_grading_batch_item (batch_id, submission_id),
                INDEX idx_grading_batch_item_batch (batch_id, status),
                INDEX idx_grading_batch_item_submission (submission_id)
            )
        """))

        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                request_id CHAR(36) NOT NULL,
                timestamp TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                user_id INT,
                action VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id INT,
                old_value JSON,
                new_value JSON,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                outcome VARCHAR(20) NOT NULL,
                method VARCHAR(10) NOT NULL,
                path VARCHAR(500) NOT NULL,
                status_code INT NOT NULL,
                CONSTRAINT fk_audit_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE SET NULL,
                INDEX idx_audit_time (timestamp),
                INDEX idx_audit_user (user_id, timestamp),
                INDEX idx_audit_resource
                    (resource_type, resource_id, timestamp)
            )
        """))

        await connection.execute(text("""
            CREATE TABLE IF NOT EXISTS knowledge_relations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                prerequisite_id INT NOT NULL,
                target_id INT NOT NULL,
                relation_type VARCHAR(30) NOT NULL DEFAULT 'prerequisite',
                strength DECIMAL(3,2) NOT NULL DEFAULT 1.00,
                CONSTRAINT fk_knowledge_relation_prerequisite
                    FOREIGN KEY (prerequisite_id) REFERENCES knowledge_points(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_knowledge_relation_target
                    FOREIGN KEY (target_id) REFERENCES knowledge_points(id)
                    ON DELETE CASCADE,
                UNIQUE KEY uk_knowledge_relation
                    (prerequisite_id, target_id, relation_type)
            )
        """))

        question_columns = await _column_names(connection, "questions")
        if "difficulty" not in question_columns:
            await connection.execute(text(
                "ALTER TABLE questions ADD COLUMN difficulty "
                "DECIMAL(4,2) NOT NULL DEFAULT 0.00 COMMENT 'IRT题目难度b'"
            ))
        if "discrimination" not in question_columns:
            await connection.execute(text(
                "ALTER TABLE questions ADD COLUMN discrimination "
                "DECIMAL(4,2) NOT NULL DEFAULT 1.00 COMMENT 'IRT区分度a'"
            ))

        mastery_columns = await _column_names(
            connection, "student_knowledge_mastery"
        )
        if "ability_theta" not in mastery_columns:
            await connection.execute(text(
                "ALTER TABLE student_knowledge_mastery ADD COLUMN ability_theta "
                "DECIMAL(5,3) NOT NULL DEFAULT 0.000 COMMENT 'IRT能力值theta'"
            ))
        if "attempt_count" not in mastery_columns:
            await connection.execute(text(
                "ALTER TABLE student_knowledge_mastery ADD COLUMN attempt_count "
                "INT NOT NULL DEFAULT 0"
            ))
        if "success_sum" not in mastery_columns:
            await connection.execute(text(
                "ALTER TABLE student_knowledge_mastery ADD COLUMN success_sum "
                "DECIMAL(8,3) NOT NULL DEFAULT 0.000 COMMENT '历次得分比例之和'"
            ))
