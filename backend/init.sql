CREATE DATABASE IF NOT EXISTS ai_homework
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ai_homework;

-- 用户表
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    role ENUM('teacher', 'student') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 班级表
CREATE TABLE classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    grade VARCHAR(50),
    invite_code VARCHAR(20) NOT NULL UNIQUE COMMENT '邀请码，班主任通过此码邀请学生',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 班级成员表（班主任、老师、学生都在一个"群"里）
CREATE TABLE class_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    class_id INT NOT NULL,
    user_id INT NOT NULL,
    role ENUM('head_teacher', 'teacher', 'student') NOT NULL DEFAULT 'student',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_class_member (class_id, user_id),
    UNIQUE KEY uk_student_one_class ((CASE WHEN role = 'student' THEN user_id END))
);

-- 学科表
CREATE TABLE subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);

-- 知识点表（支持层级结构）
CREATE TABLE knowledge_points (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subject_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    parent_id INT DEFAULT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (parent_id) REFERENCES knowledge_points(id)
);

-- 知识点关系表（用于查询前置知识依赖）
CREATE TABLE knowledge_relations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prerequisite_id INT NOT NULL,
    target_id INT NOT NULL,
    relation_type VARCHAR(30) NOT NULL DEFAULT 'prerequisite',
    strength DECIMAL(3,2) NOT NULL DEFAULT 1.00,
    FOREIGN KEY (prerequisite_id) REFERENCES knowledge_points(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES knowledge_points(id) ON DELETE CASCADE,
    UNIQUE KEY uk_knowledge_relation (prerequisite_id, target_id, relation_type)
);

-- 作业表
CREATE TABLE assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    class_id INT NOT NULL,
    subject_id INT NOT NULL,
    teacher_id INT NOT NULL,
    due_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (teacher_id) REFERENCES users(id)
);

-- 题目表（作业中的每道题）
CREATE TABLE questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    question_number INT NOT NULL,
    content TEXT,
    answer TEXT COMMENT '标准答案',
    max_score DECIMAL(5,1) NOT NULL DEFAULT 0,
    knowledge_point_id INT,
    difficulty DECIMAL(4,2) NOT NULL DEFAULT 0.00 COMMENT 'IRT题目难度b',
    discrimination DECIMAL(4,2) NOT NULL DEFAULT 1.00 COMMENT 'IRT区分度a',
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points(id)
);

-- 提交记录表
CREATE TABLE submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    student_id INT NOT NULL,
    status ENUM('pending', 'grading', 'completed') DEFAULT 'pending',
    total_score DECIMAL(6,1),
    comment TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    graded_at TIMESTAMP NULL,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (student_id) REFERENCES users(id)
);

-- 提交图片表（支持多页作业）
CREATE TABLE submission_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    submission_id INT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    page_number INT NOT NULL DEFAULT 1,
    recognized_text TEXT COMMENT 'OCR识别结果',
    FOREIGN KEY (submission_id) REFERENCES submissions(id)
);

-- 批改结果表（每道题的得分与反馈）
CREATE TABLE grading_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    submission_id INT NOT NULL,
    question_id INT NOT NULL,
    score DECIMAL(5,1),
    feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);

-- 批改批次汇总表
CREATE TABLE grading_batches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    teacher_id INT NOT NULL,
    total_submissions INT NOT NULL DEFAULT 0,
    completed_submissions INT NOT NULL DEFAULT 0,
    failed_submissions INT NOT NULL DEFAULT 0,
    status ENUM('pending', 'grading', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (teacher_id) REFERENCES users(id),
    INDEX idx_grading_batch_assignment (assignment_id, created_at),
    INDEX idx_grading_batch_teacher (teacher_id, created_at)
);

-- 批次内提交明细，避免重复计数并保留单项失败信息
CREATE TABLE grading_batch_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    submission_id INT NOT NULL,
    task_id VARCHAR(100),
    status ENUM('queued', 'grading', 'completed', 'failed') NOT NULL DEFAULT 'queued',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (batch_id) REFERENCES grading_batches(id) ON DELETE CASCADE,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
    UNIQUE KEY uk_grading_batch_item (batch_id, submission_id),
    INDEX idx_grading_batch_item_batch (batch_id, status),
    INDEX idx_grading_batch_item_submission (submission_id)
);

-- 批改历史版本表
CREATE TABLE grading_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    submission_id INT NOT NULL,
    attempt_number INT NOT NULL,
    status ENUM('started', 'completed', 'failed', 'skipped') NOT NULL DEFAULT 'started',
    total_score DECIMAL(6,1),
    raw_ocr_result JSON,
    result_snapshot JSON,
    grader_version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    error_message TEXT,
    duration_ms INT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
    UNIQUE KEY uk_submission_attempt (submission_id, attempt_number),
    INDEX idx_grading_attempt_submission (submission_id, started_at)
);

-- 只追加、不更新的操作审计表
CREATE TABLE audit_logs (
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
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_audit_time (timestamp),
    INDEX idx_audit_user (user_id, timestamp),
    INDEX idx_audit_resource (resource_type, resource_id, timestamp)
);

-- 学生知识点掌握度表
CREATE TABLE student_knowledge_mastery (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    knowledge_point_id INT NOT NULL,
    mastery_level DECIMAL(3,2) DEFAULT 0.00 COMMENT '0.00 ~ 1.00',
    ability_theta DECIMAL(5,3) NOT NULL DEFAULT 0.000 COMMENT 'IRT能力值theta',
    attempt_count INT NOT NULL DEFAULT 0,
    success_sum DECIMAL(8,3) NOT NULL DEFAULT 0.000 COMMENT '历次得分比例之和',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points(id),
    UNIQUE KEY uk_student_kp (student_id, knowledge_point_id)
);

-- 初始数据：学科
INSERT INTO subjects (name, description) VALUES
('数学', '数学学科'),
('语文', '语文学科'),
('英语', '英语学科');
