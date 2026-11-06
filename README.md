# 视源股份-AI智能批改作业系统

> **Python 后端环境**：使用 conda 环境 `fastapi`（`conda activate fastapi`）

## 赛道简介

一个班40份作业，每份都需要判对错、写评语、分析薄弱点——这是老师们每天都在面对的高强度重复工作。本赛道邀请参赛者打造一款AI智能作业批改系统，支持多学科作业的自动批改，不仅能判断对错，更能输出个性化评语和知识点薄弱分析，真正做到"每个学生都被认真对待"。

## 核心能力要求

- 多学科支持：至少覆盖2个学科（如数学计算题批改 + 语文/英语作文评改）
- 手写体识别：准确识别学生手写内容，包括公式、汉字、英文等
- 智能判分：不仅判断对错，还能识别部分正确的解题过程并给予过程分
- 个性化评语生成：针对每份作业生成有针对性的评语，而非千篇一律的模板
- 知识点薄弱分析：汇总学生的错误模式，定位薄弱知识点，输出学情分析报告

## 交付要求

- 可运行的多学科批改Demo
- 批改样例展示：输入作业图片 → 输出批改结果 + 评语 + 薄弱点分析
- 技术说明文档（OCR方案、知识建模、评语生成策略）

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| **后端** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) | ASGI 异步框架，类型安全 |
| **数据库** | MySQL 8.0 (主), Redis 7 (缓存) | 关系型 + 缓存 |
| **消息队列** | RabbitMQ 3.13, Celery 5.4 | 异步任务分发 |
| **对象存储** | MinIO | 作业图片存储 |
| **AI/OCR** | PaddleOCR (独立微服务) | 手写识别 |
| **数学引擎** | SymPy 1.14, latex2sympy2 | LaTeX 转 AST + 表达式等价判定 |
| **前端** | Vue 3 + TypeScript, Vite, Pinia, Vue Router | 组合式 API + 类型安全 |
| **部署** | Docker Compose, Nginx | 一键编排 |

## 目录结构

```
ai_homework/
├── backend/                     # FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # 应用入口，注册路由
│   │   ├── config.py            # 环境配置（DB/Redis/RabbitMQ/MinIO/OCR/LLM）
│   │   ├── database.py          # SQLAlchemy 异步引擎
│   │   ├── models.py            # 14 个 ORM 模型
│   │   ├── auth.py              # JWT 认证路由
│   │   ├── dependencies.py      # get_current_user / require_role 依赖
│   │   ├── health.py            # 多服务健康检查
│   │   ├── seed.py              # 演示数据初始化
│   │   ├── worker.py            # Celery 任务定义
│   │   ├── schemas.py           # Pydantic 数据模型
│   │   ├── grading.py           # 旧 mock 批改（保留兼容）
│   │   ├── grade_assignment.py  # 学科路由调度器
│   │   ├── knowledge_profile.py # IRT 掌握度更新
│   │   ├── learning_reports.py  # 个人/班级学情聚合
│   │   ├── report_cache.py      # Redis 报告缓存
│   │   ├── audit_service.py     # 追加式持久审计写入
│   │   ├── grading_history.py   # 批改尝试版本与快照
│   │   ├── schema_migrations.py # 幂等数据库增量迁移
│   │   ├── math_pipeline.py     # 数学批改流水线（SymPy）
│   │   ├── ocr_client.py        # OCR 微服务 HTTP 客户端
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── auth.py          # 登录/注册/刷新令牌
│   │       ├── classes.py       # 班级 CRUD
│   │       ├── assignments.py   # 作业管理（含题目/答案）
│   │       ├── submissions.py   # 提交批改（含图片/OCR/自动评分）
│   │       ├── students.py      # 学生列表
│   │       ├── knowledge.py     # 知识图谱与掌握度
│   │       ├── reports.py       # 个人/班级学情报告
│   │       └── history.py       # 批改版本与审计历史查询
│   ├── init.sql                 # MySQL 建库建表 + 初始数据
│   ├── requirements.txt         # Python 依赖（21 个）
│   ├── Dockerfile
│   └── .gitignore
├── frontend/                    # Vue 3 前端
│   ├── src/
│   │   ├── api/                 # API 客户端（client/classes/assignments/submissions/students）
│   │   ├── components/          # 题目编辑、LaTeX、图片查看和 ECharts 图表
│   │   ├── layouts/             # TeacherLayout / StudentLayout
│   │   ├── router/              # 路由守卫 + 角色校验
│   │   ├── stores/              # Pinia 状态（auth store）
│   │   ├── views/
│   │   │   ├── LoginView.vue    # 登录页
│   │   │   ├── teacher/         # 教师端 6 个页面
│   │   │   │   ├── DashboardView.vue
│   │   │   │   ├── ClassesView.vue
│   │   │   │   ├── ClassDetailView.vue
│   │   │   │   ├── ClassReportView.vue
│   │   │   │   ├── AssignmentCreateView.vue
│   │   │   │   ├── AssignmentsView.vue
│   │   │   │   └── GradingReviewView.vue
│   │   │   └── student/         # 学生端 3 个页面
│   │   │       ├── AssignmentsView.vue
│   │   │       ├── SubmitView.vue
│   │   │       ├── ResultView.vue
│   │   │       └── ProfileView.vue
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.css
│   ├── package.json
│   ├── vite.config.ts
│   ├── Dockerfile               # 多阶段构建
│   └── nginx.conf               # API 反向代理
├── ocr/                         # PaddleOCR 微服务
│   ├── ocr_server.py            # FastAPI OCR 端点
│   ├── Dockerfile               # python:3.10-slim + GPU
│   └── requirements.txt
├── deploy/
│   ├── mysql-backup/            # MySQL 定时备份与隔离恢复工具
│   └── nginx-tls.conf           # 生产 TLS 入口配置
├── tests/
│   ├── test_knowledge_profile.py # IRT 掌握度单元测试（6 个）
│   └── test_math_pipeline.py    # 数学批改流水线单元测试（11 个）
├── docker-compose.yml           # 11 服务编排（业务、备份 + Prometheus/Grafana）
├── .env / .env.example          # 环境变量
├── AGENTS.md                    # AI Agent 工作指令文档
├── claude-progress.md           # 会话进度日志
├── feature_list.json            # 功能追踪（25 个功能项）
├── init.ps1                     # Windows 统一启动脚本（需修复编码）
└── README.md                    # ← 本文件
```

## 后端架构

```
请求 → Nginx → FastAPI main.py
                 ├── /api/auth/*          (JWT 登录/注册)
                 ├── /api/health          (服务健康检查)
                 ├── /api/classes/*       (班级管理)
                 ├── /api/assignments/*   (作业 CRUD)
                 ├── /api/submissions/*   (提交批改)
                 ├── /api/students/*      (学生列表)
                 ├── /api/knowledge/*     (知识图谱与掌握度)
                 ├── /api/reports/*       (个人/班级学情报告)
                 └── require_role 中间件   (RBAC 权限控制)

提交批改流程：
POST /api/submissions → 创建 Submission → auto_grade=true
  → grade_submission() 调度器
      ├── subject_id=1 (数学) → MathGradingPipeline (SymPy)
      ├── subject_id=2 (语文) → ChineseGradingPipeline (可解释规则)
      └── subject_id=3 (英语) → EnglishGradingPipeline (可解释规则)
  → OCR 自动调用 → 逐题评分 → 生成评语 → 更新掌握度
```

## 数据存储层

系统使用四种存储服务，各司其职：

| 服务 | 用途 | 说明 |
|---|---|---|
| **MySQL 8.0** | 关系型主库 | 用户、班级、作业、提交记录、批改结果等全部业务数据 |
| **Redis 7** | 缓存 + 消息桥接 | JWT 令牌黑名单、批改结果缓存、Celery 结果后端 |
| **RabbitMQ 3.13** | 消息队列 | 异步批改任务、学情报告生成任务分发 |
| **MinIO** | 对象存储 | 学生上传的作业图片、OCR 结果缓存 |

### MySQL 表结构（14 张表）

```
users ──┬──< class_members ──> classes     (班主任/老师/学生都在同一张关联表)
        ├──< assignments      (老师布置作业)
        ├──< submissions      (学生提交作业)
        └──< student_knowledge_mastery (知识点掌握度)

subjects ──< knowledge_points (知识点归属学科，支持树形层级)
knowledge_points ──< knowledge_relations (前置知识依赖图)

assignments ──< questions     (作业包含若干题目，每道题有标准答案)

submissions ──< submission_images  (提交的多页作业图片，含 OCR 识别结果)
            ├──< grading_results  (每道题的批改得分与评语)
            └──< grading_attempts (每次批改的版本、快照与状态)

users ──< audit_logs             (追加式操作审计；用户删除后保留记录)
```

| 表名 | 字段 | 说明 |
|---|---|---|
| **users** | id, username(unique), password_hash(bcrypt+pepper), display_name, role(teacher/student), created_at, updated_at | 用户表，老师与学生统一存储 |
| **classes** | id, name, grade, invite_code(unique, 8位随机码), created_at, updated_at | 班级表，invite_code 供学生加入 |
| **class_members** | id, class_id, user_id, role(head_teacher/teacher/student), joined_at | 班级成员关联表，支持班主任/老师/学生三种角色 |
| **subjects** | id, name(数学/语文/英语), description | 学科 |
| **knowledge_points** | id, subject_id, name, parent_id | 知识点，parent_id 支持树形层级 |
| **knowledge_relations** | prerequisite_id, target_id, relation_type, strength | 知识点前置依赖关系 |
| **assignments** | id, title, class_id, subject_id, teacher_id, due_date, created_at | 作业，关联班级+学科+出题老师 |
| **questions** | id, assignment_id, question_number, content, **answer**(标准答案), max_score, knowledge_point_id, difficulty, discrimination | 作业题目，含标准答案和 IRT 参数 |
| **submissions** | id, assignment_id, student_id, status(pending/grading/completed), total_score, comment, submitted_at, graded_at | 学生提交记录 |
| **submission_images** | id, submission_id, image_path, page_number, **recognized_text**(OCR识别结果) | 提交的作业图片，支持多页 + OCR 文本缓存 |
| **grading_results** | id, submission_id, question_id, score(DECIMAL 5,1), feedback, created_at | 每道题的批改得分与评语 |
| **grading_attempts** | id, submission_id, attempt_number, status, total_score, raw_ocr_result, result_snapshot, grader_version, error_message, duration_ms, started_at, completed_at | 每次批改的不可覆盖版本快照 |
| **audit_logs** | id, request_id, timestamp, user_id, action, resource_type, resource_id, outcome, status_code, old_value, new_value | 追加式持久审计记录；不保存通用请求体、图片、IP 或 User-Agent |
| **student_knowledge_mastery** | student_id, knowledge_point_id, mastery_level, ability_theta, attempt_count, success_sum, updated_at | 学生知识点能力和掌握度持续追踪 |

### 核心业务链路

```
老师创建班级 → 添加学生 → 布置作业（含题目&标准答案）→ 学生提交图片
    ↓
MinIO 存储图片 → OCR 识别（独立微服务）→ 识别文本存入 MySQL
    ↓
学科路由调度器 → 数学(SymPy) / 语文(模板) / 英语(模板) → 逐题评分
    ↓
生成评语 + 更新知识点掌握度 → 结果缓存到 Redis → 通知前端
```

## API 端点一览

| 方法 | 路径 | 角色 | 说明 |
|---|---|---|---|
| POST | /api/auth/register | - | 用户注册 |
| POST | /api/auth/login | - | 登录获取 JWT |
| POST | /api/auth/refresh | - | 刷新令牌 |
| GET | /api/health | - | 健康检查 |
| GET | /api/classes | teacher/student | 班级列表 |
| GET | /api/classes/{id} | teacher/student | 班级详情（含成员） |
| POST | /api/classes | teacher | 创建班级 |
| POST | /api/classes/{id}/students | teacher | 添加学生 |
| GET | /api/assignments | teacher/student | 作业列表 |
| GET | /api/assignments/{id} | teacher/student | 作业详情（含题目+答案） |
| POST | /api/assignments | teacher | 布置作业 |
| GET | /api/submissions | teacher/student | 提交记录列表 |
| GET | /api/submissions/{id} | teacher/student | 提交详情（含评分） |
| POST | /api/submissions | student | 提交作业（触发自动批改） |
| POST | /api/submissions/{id}/grade | teacher | 手动触发批改 |
| GET | /api/history/submissions/{id}/attempts | teacher | 查询受管班级提交的批改版本历史 |
| GET | /api/history/submissions/{id}/audit | teacher | 查询受管班级提交的审计历史 |
| GET | /api/students | teacher | 学生列表 |

批改开始时系统创建递增的 `grading_attempts.attempt_number`，结束后保存 OCR、逐题结果、总分、评语、耗时和批改器版本快照；失败或跳过也保留终态。审计中间件同时把认证、拒绝访问、限流和数据变更写入 `audit_logs`。两类历史接口仅允许教师查询自己管理班级中的提交，且响应不暴露 IP 或 User-Agent。当前审计表保留外键和常规索引，尚未按 `方案文档.md` 的建议做 MySQL 月分区。

## 演示账户

Docker 启动后自动创建以下演示账户（密码均为 `demo123`）：

| 用户名 | 显示名 | 角色 | 说明 |
|---|---|---|---|
| `math_teacher` | 张老师 | teacher | 数学老师兼班主任（六年级一班） |
| `chinese_teacher` | 李老师 | teacher | 语文老师 |
| `english_teacher` | 王老师 | teacher | 英语老师 |
| `student_a` | 学生A | student | 六年级一班学生 |

## 启动方式

### 本地开发

```bash
# 1. 启动后端（conda 环境）
conda activate fastapi
uvicorn backend.main:app --reload --port 8000

# 2. 新开终端，启动前端
cd frontend
npm install    # 首次需安装依赖
npm run dev    # 开发服务器，API 自动代理到 :8000
```

### Docker 部署

首次启动需配置 Docker Desktop 代理（使用梯子）：
- Docker Desktop → 设置 → Resources → Proxies
- Manual proxy(依次填入): `http://127.0.0.1:7890`、`http://127.0.0.1:7890`、`localhost,127.0.0.1,.docker.internal`(其中，7890是梯子的代理端口，直接在梯子软件就可以看到)
- Containers proxy: Same as host proxy

```bash
# 构建并启动全部 11 个服务（含业务栈、MySQL 备份、Prometheus 和 Grafana）
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:8080 |
| 后端 API | http://localhost:8000 |
| 健康检查 | http://localhost:8000/api/health |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| MinIO 控制台 | http://localhost:9001 |
| RabbitMQ 管理 | http://localhost:15672 |

### 监控与日志

- `GET http://localhost:8000/metrics` 返回 Prometheus 指标。
- Prometheus 每 5 秒抓取 backend；Grafana 已自动配置 Prometheus 数据源和 `AI Homework Grading Overview` 仪表盘。
- Grafana 默认账号是 `admin`，密码读取 `.env` 中的 `GRAFANA_ADMIN_PASSWORD`，未配置时为 `admin`。部署环境请务必修改。
- backend 和 Celery Worker 的应用日志输出为 JSON，包含请求 ID、路由、状态码、任务状态和耗时等字段。
- 指标数据保存在 `prometheus_multiproc` 卷中；需要清空本地指标时执行 `docker compose down -v`，该命令会同时删除其他 Compose 数据卷。

### 数据备份与恢复

`mysql-backup` 服务启动后立即执行一次逻辑备份，之后每天在 `MYSQL_BACKUP_TIME`（默认 `03:00`）运行。备份使用 `mysqldump --single-transaction`，先写临时文件，再压缩、执行 gzip/ SHA-256 校验并原子改名；成品同时保存在 `mysql_backups` 命名卷和 MinIO 的 `ai-homework-backups/mysql/`。本地与 MinIO 备份默认保留 30 天。

```powershell
# 立即生成一份备份
docker compose exec -T mysql-backup /usr/local/bin/backup.sh once

# 从 MinIO 下载最新备份，导入隔离临时库，检查 14 张表后自动删除临时库
docker compose exec -T mysql-backup /usr/local/bin/restore.sh verify

# 恢复指定备份到新的数据库；默认拒绝覆盖 ai_homework 主库
docker compose exec -T mysql-backup /usr/local/bin/restore.sh restore full_YYYYMMDD_HHMMSS.sql.gz ai_homework_recovery

# 执行可重复的备份、MinIO、隔离恢复、清理和覆盖保护集成测试
powershell.exe -ExecutionPolicy Bypass -File tests/integration_mysql_backup.ps1
```

恢复工具默认从 MinIO 取文件并强制核对同名 `.sha256`；只有显式指定 `RESTORE_SOURCE=local` 才从本地卷读取。主库恢复属于停机运维操作，应先完成隔离验证并另行保留当前数据，本地常规开发不需要解除覆盖保护。

## 测试与验证

首次运行本地测试前安装开发依赖：

```powershell
python -m pip install -r backend/requirements-dev.txt
cd frontend
npm install
npx playwright install chromium
cd ..
```

在仓库根目录执行后端测试和覆盖率门槛：

```powershell
python -m pytest --cov=backend/app --cov-fail-under=85 -q
```

Docker Desktop 和 Compose 服务运行后，执行 Testcontainers 及业务集成测试：

```powershell
powershell.exe -ExecutionPolicy Bypass -File tests/run_docker_tests.ps1
```

执行三条真实 Docker 浏览器工作流。脚本会创建隔离的临时教师、学生、班级和作业，并在成功或失败后自动清理数据库、Redis 缓存和 MinIO 对象：

```powershell
powershell.exe -ExecutionPolicy Bypass -File tests/run_browser_e2e.ps1
```

执行前端生产构建与 Playwright E2E：

```powershell
cd frontend
npm run build
npm run test:e2e
```

当前自动化基线为后端 `131 passed, 1 skipped`、覆盖率 `85.38%`，快速 Mock Chromium E2E `1 passed`，真实 Docker Chromium E2E `3 passed`。完整 Docker 脚本还验证了 Redis Testcontainers、MySQL 备份/隔离恢复、私有 MinIO 上传、RabbitMQ/Celery、WebSocket、评分版本、持久审计、知识画像和报告缓存。Testcontainers 用例在普通 pytest 中默认跳过，只由 Docker 集成脚本显式启用。

## CI/CD

`.github/workflows/ci.yml` 会在 `main` 的 push 和 Pull Request 上执行：

- Python Ruff lint 和 pytest 覆盖率门（至少 85%）。
- 前端 `npm ci`、TypeScript/生产构建和 Chromium Playwright E2E。
- backend、frontend Docker 镜像构建。

推送 `v*` 标签时，工作流还会把 backend 和 frontend 镜像发布到 GitHub Container Registry（GHCR）。当前没有配置具体服务器、域名或部署凭据，因此工作流暂不执行远程主机部署。

当前 Git 远端位于 GitCode，不会执行 GitHub Actions。要启用这份工作流，需要把仓库迁移或镜像到 GitHub；继续使用 GitCode 时，应按其 CI 平台规范改写流水线。

## 安全部署

默认 Compose 用于本地开发。生产 TLS 覆盖要求 Docker Compose 2.24.4+，证书目录必须包含 `fullchain.pem` 和 `privkey.pem`：

```powershell
$env:TLS_SERVER_NAME = "homework.example.com"
$env:TLS_CERT_DIR = "C:\path\to\certificate-directory"
$env:CORS_ALLOWED_ORIGINS = "https://homework.example.com"
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
```

TLS 覆盖只向宿主机发布 80/443，HTTP 自动跳转 HTTPS，Nginx 只启用 TLS 1.3。登录默认限流 5 次/分钟，其余 API 默认 60 次/分钟，可通过 `.env` 调整。审计事件同时写入 backend JSON 日志和 MySQL `audit_logs`：

```powershell
docker compose logs backend | Select-String security_audit
```
