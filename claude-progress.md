# 进度日志

## 当前已验证状态

- 仓库根目录：项目所在目录（不要在文档中固化个人绝对路径）
- 标准启动路径：`docker compose up -d --build`
- 标准验证路径：`python -m pytest --cov=backend/app --cov-fail-under=85 -q`、`tests/run_docker_tests.ps1`、`frontend/npm run test:e2e`
- 当前已完成：grading-003（语文批改流水线）、grading-004（英语批改流水线）、grading-005（Celery 批改调度器）、comment-001（LLM 个性化评语）、comment-002（模板保底评语）、profile-001（知识点图谱 + IRT 掌握度）、profile-002（学情分析报告）、frontend-003（批改展示核心组件）、quality-001（可观测性）、quality-002（自动化测试体系）、quality-004（安全加固）
- 当前延期功能：grading-001（OCR 图片级识别结果验证，等待真实手写样本）
- OCR 清晰印刷中文及完整链路已验证；手写汉字和手写数学公式准确率仍待真实样本人工确认
- 当前阻塞：quality-003（现有 origin 是 GitCode，无法触发 GitHub Actions）；grading-001（等待真实手写样本）
- 下一步决策：选择迁移/镜像到 GitHub，或将流水线改写为 GitCode CI；真实外部 LLM 和真实数据视觉验收仍保留为人工验收

### Session 018 - quality-004 security hardening

- Added Redis-backed fixed-window rate limiting with atomic Lua counters and process-local failover: login 5/minute, other API routes 60/minute, configurable through environment variables.
- Added structured security audit events for authentication, access denial, rate limiting, and mutating requests; logs include request ID, actor ID, pseudonymous client ID, action, outcome, path, and status.
- Rejects refresh tokens at protected API dependencies, validates external request IDs as UUIDs, and restricts CORS to configured origins.
- Strengthened OCR upload checks so PNG/JPEG extensions must match magic bytes in addition to existing size and type limits.
- Added Nginx CSP and security response headers plus a TLS 1.3 Compose deployment overlay that exposes only 80/443 and requires deployment-provided certificates.
- Verification: Ruff passed; pytest `104 passed, 1 skipped`, coverage `86.80%`; frontend build and Playwright E2E passed; backend/frontend images rebuilt; real HTTP login attempt 6 returned 429 with Retry-After; 429 metrics and JSON audit logs appeared; security headers were returned; TLS config passed `nginx -t` with a temporary certificate; Docker integration runner passed after test-client isolation.
- Commits: `95c7ffd`, `7813eef`, `16c0d30`, `7e49a7d`.
- Known limitations: production certificates, domain DNS, external firewall, and key rotation remain deployment responsibilities. The existing bcrypt/passlib compatibility warning and datetime deprecations remain non-blocking maintenance items.

### Session 016 - quality-002 automated test system

- Added pytest configuration, coverage rules, shared fixtures, and focused tests for authentication, RBAC, cache, health, routers, grading, mastery persistence, reports, and Worker behavior.
- Fixed two grading defects exposed by tests: missing-assignment error handling and empty low-score feedback template selection.
- Added a Python 3.13-compatible simple LaTeX fallback while retaining the full parser when available.
- Added a Testcontainers Redis smoke test and `tests/run_docker_tests.ps1` for Celery grading, knowledge profile, learning report, permission, cache, and invalidation integration checks.
- Added Playwright Chromium E2E for the deterministic student login → assignment → submit → grading result flow.
- Final verification: `95 passed, 1 skipped`, backend coverage `86.58%` (threshold `85%`), frontend production build passed, Playwright `1 passed`, Docker integration runner passed twice including after backend/Worker image rebuild, and all 10 Compose services were running.
- Commits: `f8e03ef`, `ff9a8c3`, `f21d09d`, `7cd498b`, `fcfc5f9`, `a9cbb57`, `833c720`.
- Known limitations: real handwritten OCR image acceptance remains deferred under grading-001; pytest cache may warn about local Windows directory permissions; FastAPI startup and `datetime.utcnow()` deprecation warnings remain; npm audit reports 1 moderate and 2 high vulnerabilities and no forced major upgrade was applied.

### Session 017 - quality-003 CI/CD workflow

- Added `.github/workflows/ci.yml` with separate backend quality, frontend quality, Docker build, and tag-based GHCR publish jobs.
- Backend CI installs pinned development dependencies, runs Ruff and the 85% coverage gate. Frontend CI uses `npm ci`, production build, Chromium installation, and Playwright E2E with failure artifacts.
- Docker CI builds backend and frontend images after the quality jobs. `v*` tags publish both application images to GHCR using the built-in `GITHUB_TOKEN`.
- Added `pyproject.toml` Ruff configuration, fixed unused imports/variables, and made frontend Docker builds reproducible with `package-lock.json`, `npm ci`, and Docker ignore files.
- Local verification passed: workflow YAML parsed, Ruff passed, pytest passed with 95 passed/1 skipped and 86.57% coverage, frontend build and E2E passed, backend/frontend image builds passed, and `docker compose config -q` passed.
- Commit: `0c8b8fc` (lint gate), `7e10cb3` (CI workflow and Docker build reproducibility).
- Pending evidence: the repository must run the workflow on GitHub once before quality-003 can be marked passing; remote host deployment remains unconfigured.

### Session 015 - quality-001 observability (Prometheus + Grafana)

- Implemented `backend/app/observability.py` with HTTP request counters, latency histograms, grading task counters, grading latency histograms, retry counters, `/metrics`, request IDs, and JSON logging.
- Instrumented `backend/app/worker.py`; Celery grading attempts record subject, status, duration, retry events, and structured task logs.
- Added Prometheus `9090` and Grafana `3000` to Compose. Grafana provisions the Prometheus data source and the `AI Homework Grading Overview` dashboard.
- Added `tests/test_observability.py`; all 4 observability checks and all 3 existing Worker checks passed.
- Docker verification passed: backend healthy, Prometheus target `ai-homework-backend` is `up`, Grafana health is `ok`, dashboard is provisioned, and a temporary Celery grading task completed with `ai_homework_grading_tasks_total{status="completed",subject="chinese"}`.
- Commits: `9bf3e1f`, `7d8b139`, `780c527`, `af604e1`, `52e75ea`, `84957c0`.
- Known limitations: Grafana's bundled plugin may log a duplicate `xychart` registration warning; Celery still runs as root in the existing Compose setup. Real handwritten OCR validation remains deferred.

## 会话记录

### Session 014 — frontend-003 批改展示核心组件

- 日期：2026-07-19
- 本轮目标：把知识掌握度、班级分布和逐题批改结果做成可复用、可响应式展示的前端组件
- 已完成：
  - 添加 `echarts` 和维护中的 `@lucide/vue`；未保留已弃用的 `lucide-vue-next`
  - `EChartSurface.vue` — 按需注册 radar/bar/line、tooltip、grid、radar 和 Canvas renderer，监听容器尺寸
  - `KnowledgeRadar` / `ScoreDistribution` / `TrendChart` — 掌握度雷达、分布和真实历史趋势组件
  - `ImageViewer` — 放大、缩小、重置、双页对比和加载失败状态
  - `StepComparison` — 逐题完成度、得分和反馈对比
  - 学生新增“我的学情”，教师班级详情新增“班级学情”，批改详情接入图片和图表组件
  - ECharts 从全量约 1.03 MB 分包优化到按需约 494 KB，无 chunk 大小警告
- 运行过的验证：
  - `npm run build` 通过，Vue TypeScript 严格检查通过
  - `docker compose build frontend` 多阶段构建通过
  - 新路由、报告 API 类型、空状态、错误状态和移动端 CSS 均进入生产构建
- 提交记录：
  - `7375d35 feat: add report frontend dependencies and types`
  - `aca9f4b feat: add grading visualization components`
  - `33acf98 feat: integrate learning reports and grading views`
- 已知风险或未解决问题：
  - bundled Playwright 缺少 `playwright-core`，自动桌面/手机截图未执行，不能声称视觉截图已验收
  - npm audit 报告 1 个 moderate 漏洞，未使用可能引入破坏性升级的 `audit fix --force`
  - 趋势组件等待后端历史快照数据，目前显示明确空状态
  - 图片 URL 仍依赖后端真实对象存储访问地址，模拟本地路径会显示加载失败状态
- 下一步最佳动作：实现 quality-001 可观测性；前端页面由用户后续在浏览器中进行真实数据和移动端人工验收

### Session 013 — profile-002 学情分析报告生成

- 日期：2026-07-19
- 本轮目标：为学生生成个人画像、为教师生成班级学情聚合，并使用 Redis 缓存减少重复查询
- 已完成：
  - `backend/app/learning_reports.py` — 个人总览、学科汇总、雷达数据、优势/薄弱点和班级知识点/学生聚合
  - `backend/app/report_cache.py` — Redis JSON 缓存、300 秒默认 TTL、个人/班级模式失效和故障降级
  - `backend/app/routers/reports.py` — 学生个人报告与教师班级报告接口
  - 教师只能查看自己班级及班级学生；学生只能查看自己，越权返回 403
  - `backend/app/grade_assignment.py` — 掌握度更新提交后清除相关个人和班级报告缓存
  - `tests/integration_learning_reports.py` — 验证报告、缓存命中、权限、Celery 更新和缓存失效
- 运行过的验证：
  - 报告聚合 6/6、知识点算法 6/6、语文 7/7、英语 7/7、评语 7/7、LLM 6/6、调度 3/3、worker 3/3、OCR 2/2 通过
  - Docker 报告集成通过：个人/班级聚合、Redis miss→hit、学生越权 403、批改后两个缓存重新 miss、数据清理完成
  - Docker 数学规则 11/11、旧英语 Celery 18.9/20 通过
  - Docker backend/Celery 镜像构建通过，8 个 Compose 服务继续运行
- 提交记录：
  - `056478a feat: add learning report aggregations`
  - `c0df2d4 feat: add cached learning report API`
  - `66eb20d test: verify cached learning reports`
- 已知风险或未解决问题：
  - 当前只有最新掌握度快照，没有历史快照表，因此未生成虚假的趋势曲线
  - Redis 采用按 key 模式扫描失效，当前课程项目规模合适；大规模部署应改为版本化 key 或集合索引
  - API 已输出雷达图数据，真正的前端 ECharts 图表尚待 frontend-003
- 下一步最佳动作：实现 frontend-003，优先做 KnowledgeRadar、ScoreDistribution 和批改审核视图的数据接入

### Session 012 — profile-001 知识点图谱 + IRT 掌握度

- 日期：2026-07-19
- 本轮目标：批改完成后按题目知识点更新学生掌握度，并提供可查询的前置知识图谱和薄弱点状态
- 已完成：
  - `backend/app/models.py` / `backend/init.sql` — 新增 `knowledge_relations`，题目增加 IRT 难度/区分度，掌握度增加 theta、作答次数和累计正确比例
  - `backend/app/schema_migrations.py` — 对现有 MySQL volume 执行幂等增量迁移，不要求删除数据库
  - `backend/app/knowledge_profile.py` — 实现有边界的在线 2PL-IRT 更新，支持部分得分和题目难度
  - `backend/app/grade_assignment.py` — 批改结果按知识点写入或更新 `student_knowledge_mastery`
  - `backend/app/routers/knowledge.py` — 图谱查询、教师建点/建关系、教师/学生掌握度查询和权限限制
  - `tests/integration_knowledge_profile.py` — 验证 API→Celery→MySQL，并自动清理临时数据
- 运行过的验证：
  - 知识点算法 6/6、语文 7/7、英语 7/7、评语 7/7、LLM 6/6、调度 3/3、worker 3/3、OCR 校验 2/2 通过
  - Docker 数学规则 11/11 通过；Docker 旧语文 Celery 批改 17.2/20 通过，未关联知识点的旧题不创建掌握度记录
  - Docker profile 集成通过：建点/建关系、数学批改、theta/掌握度查询、学生越权 403 和清理断言全部通过
  - Docker backend/Celery 镜像构建通过，当前 MySQL volume 的新增字段和关系表已验证存在
- 提交记录：
  - `f4a0fcf feat: add knowledge profile schema`
  - `e46661b feat: add bounded IRT mastery updates`
  - `aa6810e feat: update mastery after grading`
  - `5703cd6 feat: add knowledge graph and mastery API`
  - `ea9c17a test: verify knowledge profile end to end`
- 已知风险或未解决问题：
  - 当前 IRT 参数是可解释的初始近似，尚未用真实题库进行 a/b 参数标定
  - 关系接口暂未实现环检测，复杂知识图谱需要后续增加拓扑校验
  - 前端尚未展示掌握度图表，profile-002 将负责学情报告和可视化数据聚合
- 下一步最佳动作：实现 profile-002 学情分析报告，聚合学生知识点掌握度、薄弱点和班级统计；手写图片验收继续单独安排

### Session 011 — comment-001 LLM 个性化评语

- 日期：2026-07-19
- 本轮目标：在不影响离线批改可用性的前提下，接入可配置的 OpenAI/Qwen 兼容个性化评语
- 已完成：
  - `backend/app/llm_feedback.py` — 基于现有 httpx 的 OpenAI 兼容异步客户端，无需增加 SDK 依赖
  - 支持 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、超时、输出长度和 token 参数配置
  - 提示词只发送学科、总分和最多 8 条受限逐题反馈，不发送姓名和完整 OCR 学生答案
  - 模型输出执行控制字符、脚本/提示注入、密钥和链接检测，并限制为 500 字符
  - `feedback_engine.generate_comment()` 统一执行 LLM 优先和确定性模板回退
  - `grade_submission()` 已异步生成总评语并写入 `submission.comment`
- 运行过的验证：
  - LLM 客户端 6/6、评语引擎 7/7、语文 7/7、英语 7/7、调度 3/3、worker 3/3、OCR 校验 2/2 通过
  - Docker 数学规则 11/11 通过；本机数学 LaTeX 测试因既有依赖差异失败，Docker 完整依赖环境通过
  - Docker backend、celery-worker、frontend 镜像构建通过，8 个 Compose 服务运行
  - Docker Celery 数学 16.0/20、语文 17.2/20、英语 18.9/20，均生成模板降级评语并自动清理数据
- 提交记录：
  - `da5bf20 feat: add optional LLM feedback client`
  - `09789ee feat: use personalized comments during grading`
  - `f4d4005 test: cover LLM feedback failure paths`
- 已知风险或未解决问题：
  - 当前 `.env` 未配置真实 `LLM_API_KEY`，因此没有声称真实 OpenAI/Qwen 供应商调用已经通过
  - Redis 缓存尚未实现；应在真实调用和并发数据明确后再按成本与命中率设计
  - 外部模型评语质量仍需教师抽样审核，模板引擎继续作为可靠默认路径
- 下一步最佳动作：实现 profile-001 知识点关系和学生掌握度更新；真实图片与外部模型验收稍后集中进行

### Session 010 — comment-002 模板保底评语引擎

- 日期：2026-07-19
- 本轮目标：移除随机总评语，在无 LLM 和无网络依赖时生成稳定、可解释的学科评语
- 已完成：
  - `backend/app/feedback_engine.py` — 按学科、分数区间和逐题反馈生成总评语
  - 支持高分鼓励、中间分数订正、低分基础巩固和未知学科兜底
  - 支持语文错别字/结构/相关度、英语拼写/语法/词汇/相关度、数学明确错误步骤等建议
  - `backend/app/grade_assignment.py` — 删除随机 `_pick_comment()`，批改结束后写入确定性 `submission.comment`
  - `tests/test_feedback_engine.py` — 5 个模板评语测试
  - `tests/integration_celery_grading.py` — 扩展数学、语文、英语三学科评语落库断言
- 运行过的验证：
  - 模板评语 5/5、调度 3/3、中文 7/7、英语 7/7、worker 3/3 通过
  - Docker 数学任务：16.0/20，生成数学评语并清理测试数据
  - Docker 语文任务：17.2/20，保留真实结构建议并清理测试数据
  - Docker 英语任务：18.9/20，高分评语不误报拼写/语法问题并清理测试数据
  - Docker 前端 TypeScript 检查和生产构建通过
  - 8 个 Compose 服务运行，backend/ocr/mysql/redis/rabbitmq/minio healthy
- 提交记录：
  - `a0ef1fe feat: add deterministic fallback comments`
  - `284cabd feat: generate fallback comments after grading`
  - `6648407 fix: avoid false fallback comment suggestions`
- 已知风险或未解决问题：
  - 模板建议依赖逐题反馈中的稳定标记，新批改规则增加错误类型时需同步扩展映射
  - 数学当前示例得分为 16.0/20，源于已有步骤判分权重，不是模板评语引擎改动
  - 尚未接入 LLM；下一步由 comment-001 调用外部模型，失败时回退到本模板引擎
- 下一步最佳动作：实现 comment-001 LLM 个性化评语，并保持零配置自动回退

### Session 009 — OCR 链路验证 + grading-004 英语批改流水线

- 日期：2026-07-19
- 本轮目标：回归异步批改、验证 OCR 真实链路并完成确定性英语批改
- OCR 验证与修复：
  - 自动生成清晰印刷图片，内容为“春天的校园充满阳光 / AI 作业批改测试 2026”
  - `/ocr` 返回 2 行文本；中文行置信度 0.9975，混合文本行置信度 0.9609
  - 发现 backend/worker 默认使用 `localhost:5001` 无法跨容器访问，修复为 `OCR_SERVICE_URL=http://ocr:5001`
  - `ocr_server.py` 增加空文件、10 MB 大小、PNG/JPEG 扩展名和文件魔数校验
  - 非图片文件由 500 修正为 415；缺失文件字段返回 422
  - `tests/integration_ocr_grading.py` 验证 image→OCR→Celery→MySQL：`recognized_text` 成功落库，中文得分 15.9/20，临时数据清理完成
- 英语批改实现：
  - `backend/app/english_pipeline.py` — 常见拼写、主谓一致、第三人称单数、冠词、大小写/标点、词汇多样性和主题相关度评分
  - `backend/app/grade_assignment.py` — `_grade_english` 移除随机打分并接入确定性流水线
  - `tests/test_english_pipeline.py` — 7 个英语流水线测试
  - `tests/test_grade_dispatch.py` — 英语调度和反馈维度测试
  - `tests/integration_celery_grading.py` — 支持通过 `GRADING_TEST_SUBJECT` 验证语文/英语学科
- 运行过的回归与集成验证：
  - 中文流水线 7/7、英语流水线 7/7、worker 3/3、调度层 3/3 通过
  - Docker 数学流水线 11/11 通过
  - Docker Celery 英语任务：18.9/20，生成 1 条结果并自动清理
  - Docker Celery 语文回归：17.2/20，生成 1 条结果并自动清理
  - Docker 前端 TypeScript 检查和生产构建通过
  - `docker compose ps` 显示 8 个服务运行，backend/ocr/mysql/redis/rabbitmq/minio healthy
- 提交记录：
  - `5a886c0 fix: connect grading services to validated OCR`
  - `614952f feat: add deterministic English grading pipeline`
  - `2483798 feat: route English submissions through grading pipeline`
  - `1e61212 test: verify English grading through Celery`
- 已知风险或未解决问题：
  - OCR 清晰印刷中文通过，但手写汉字和手写数学公式尚未使用真实样本验证
  - PaddleOCR 将图片中的大写 `I` 识别为数字 `1`，说明英文/数字混合文本仍可能有字符混淆
  - OCR 文件校验基于扩展名和魔数，尚未做完整图片解码与像素尺寸限制
  - 英语拼写和语法是保守规则库，复杂语义、时态和从句可能漏检
  - Celery worker 仍以 root 用户运行，生产环境应改为非 root
- 下一步最佳动作：实现 comment-002 模板保底评语，再接 comment-001 LLM 个性化评语

### Session 008 — grading-005 Celery 批改调度器

- 日期：2026-07-19
- 本轮目标：把 Celery 任务桩接入真实批改流程，使提交接口异步入队并在前端展示批改状态
- 已完成：
  - `backend/app/worker.py` — 每个任务创建独立异步数据库会话，执行真实 `grade_submission`，支持重试、`acks_late` 和单任务预取
  - `backend/app/routers/submissions.py` — 创建提交和教师手动触发改为返回 HTTP 202、`task_id`；重复入队返回 409；队列不可用返回 503 并恢复 `pending`
  - `backend/app/grade_assignment.py` — 从固定学科 ID 改为按 `Subject.name` 和英文别名选择流水线
  - 前端提交后进入结果页；学生结果页、教师详情页和审核列表轮询 `pending/grading/completed` 状态
  - `tests/test_worker.py` — 3 个 worker 和入队测试
  - `tests/integration_celery_grading.py` — 自建测试数据、真实入队、验证结果并自动清理
- 运行过的验证：
  - `python tests/test_worker.py` — 3/3 通过
  - `python tests/test_grade_dispatch.py` — 学科名称路由和中文调度测试通过
  - `python tests/test_chinese_pipeline.py` — 7/7 回归通过
  - `docker compose build frontend` — TypeScript 检查和生产构建通过
  - Docker worker 注册 `grade_submission`/`generate_report`，连接 RabbitMQ 和 Redis 成功
  - Docker 集成测试：任务入队后约 0.6 秒完成，`submission.status=completed`，中文得分 17.2/20，生成 1 条 `GradingResult`
  - 集成测试 `finally` 清理完成，并断言临时作业和用户数量为 0
  - `docker compose ps` — 8 个服务运行，backend/ocr/mysql/redis/rabbitmq/minio healthy
- 提交记录：
  - `40ab71e feat: execute grading in Celery worker`
  - `49c6df9 feat: enqueue submission grading from API`
  - `e78adfb feat: track asynchronous grading in frontend`
  - `e27a51c test: verify Celery grading end to end`
- 已知风险或未解决问题：
  - `generate_report` 仍为任务桩，本轮只完成批改队列
  - Celery worker 在 Docker 中以 root 用户运行，生产部署应改为非 root
  - API 已阻止普通重复入队，但并发重复投递尚无数据库级唯一约束
  - 前端使用 2 秒轮询，尚未实现 WebSocket 实时推送
  - OCR 图片级识别准确率仍待用户后续人工验证
- 下一步最佳动作：按用户安排实现 grading-004 英语批改流水线；OCR 真实图片验收保留为待办

### Session 007 — grading-003 语文批改流水线

- 日期：2026-07-19
- 本轮目标：实现确定性的语文作文评分，并接入 `grade_submission` 学科调度
- 已完成：
  - `backend/app/chinese_pipeline.py` — 保守短语错别字检测、重复字检测、句子通顺度、内容相关度、结构完整度评分和可读反馈
  - `backend/app/grade_assignment.py` — `subject_id == 2` 改为调用中文流水线，移除该分支随机分数和随机评语
  - `tests/test_chinese_pipeline.py` — 7 个中文流水线测试
  - `tests/test_grade_dispatch.py` — 中文调度层测试
- 运行过的验证：
  - `python tests/test_chinese_pipeline.py` — 7/7 通过
  - `python tests/test_grade_dispatch.py` — 通过
  - `docker compose build frontend` — 通过
  - Docker backend 健康，`grade_submission` 导入通过，中文评分返回确定性结果
  - Docker backend 中 SymPy + LaTeX 解析通过，数学正确答案返回 10.0/10.0
  - `docker compose ps` — backend、frontend、ocr、mysql、redis、rabbitmq、minio 均运行，backend/ocr/mysql/redis/rabbitmq/minio healthy
- 提交记录：
  - `f575f15 feat: add deterministic Chinese grading pipeline`
  - `1387993 feat: route Chinese submissions through grading pipeline`
- 已知风险或未解决问题：
  - 错别字检测是可解释的保守规则库，不是完整中文词典或 LLM 语义审校
  - 当前 `GradingResult.feedback` 以文本承载错误列表和评分维度，尚未提供独立结构化 JSON 字段
  - 本机 Conda 环境缺少 `aiomysql`、`latex2sympy2` 和前端 `node_modules`；完整依赖验证已在 Docker 环境完成
  - `init.ps1` 文件编码损坏（中文显示乱码 + 语法错误），尚未修复
- 下一步最佳动作：完成 grading-001 的 OCR 图片级验证，再实现 grading-005 的 Celery 批改任务接入

### Session 005 — grading-001 PaddleOCR 微服务集成

- 日期：2026-07-19
- 本轮目标：构建独立 OCR 微服务容器，集成到提交流程
- 已完成：
  - `ocr/ocr_server.py` — 基于 FastAPI + PaddleOCR 的微服务（/health + /ocr 端点）
  - `ocr/Dockerfile` — 基于 python:3.10-slim，含 GPU 部署能力
  - `ocr/requirements.txt` — paddlepaddle + paddleocr + fastapi 依赖
  - `docker-compose.yml` — 新增 ocr 服务（GPU resource reservation + healthcheck）
  - `backend/app/config.py` — 添加 OCR_SERVICE_URL 配置
  - `backend/app/ocr_client.py` — async HTTP 客户端调用 OCR 服务
  - `backend/app/models.py` — SubmissionImage 添加 recognized_text 字段
  - `backend/init.sql` — 同步 recognized_text 字段
  - `backend/app/grading.py` — mock_grade 集成 OCR 调用，使用 simple_text_match 评分
- 运行过的验证：
  - `cd backend && python -c "from main import app"` — 通过
  - `cd frontend && npm run build` — 通过
  - `python -c "import ast; ast.parse(open('ocr/ocr_server.py').read())"` — 语法通过
- 已记录证据：构建成功日志
- 提交记录：2d4473e feat: grading-001 PaddleOCR 微服务集成
- 更新过的文件或工件：11 个文件
- 已知风险或未解决问题：
  - OCR 服务需 `docker compose build ocr && docker compose up -d ocr` 后运行 /ocr 端点验证
  - PaddleOCR 首次加载需下载模型文件，start_period 设为 60s
  - `init.ps1` 文件编码损坏（中文显示乱码 + 语法错误），需修复
- 下一步最佳动作：grading-002 数学批改流水线（SymPy 表达式解析 + 步骤判分）

### Session 004 — POST API 422 修复

- 日期：2026-07-19
- 本轮目标：修复 POST /api/assignments 返回 422 Unprocessable Entity
- 已完成：
  - `backend/app/routers/assignments.py` — 新增 `CreateAssignmentRequest` Pydantic 模型
  - `backend/app/routers/classes.py` — 新增 `CreateClassRequest` / `AddStudentRequest` Pydantic 模型
  - `backend/app/routers/submissions.py` — 新增 `CreateSubmissionRequest` Pydantic 模型
- 运行过的验证：
  - `cd backend && python -c "from main import app"` — 通过
  - `cd frontend && npm run build` — 通过
- 已知风险或未解决问题：
  - `init.ps1` 文件编码损坏（中文显示乱码 + 语法错误），需修复
  - 学生提交流程图片使用模拟路径，需接入真实存储

### Session 003 — 模拟批改全链路 + LaTeX 编辑器

- 日期：2026-07-19
- 已完成：LaTeX 渲染组件、QuestionEditor 图文工具栏、mock_grade 批改打分
- 运行过的验证：后端 import 通过、前端构建通过

### Session 002 — 后端业务 API + 前端功能页面

- 日期：2026-07-19
- 本轮目标：开发后端核心业务 API 和前端功能页面
- 已完成：
  - `backend/app/routers/classes.py` — 班级 CRUD API（列表/详情/创建/添加学生）
  - `backend/app/routers/assignments.py` — 作业管理 API（列表/详情/创建含题目）
  - `backend/app/routers/submissions.py` — 提交批改 API（列表/详情/创建）
  - `backend/app/routers/students.py` — 学生列表 API
  - `backend/main.py` — 注册所有新路由
  - `frontend/src/api/classes.ts` / `assignments.ts` / `submissions.ts` / `students.ts` — 前端 API 客户端
  - `frontend/src/views/teacher/ClassesView.vue` — 班级列表 + 创建班级
  - `frontend/src/views/teacher/ClassDetailView.vue` — 班级详情 + 添加学生 + 作业/提交概览
  - `frontend/src/views/teacher/AssignmentCreateView.vue` — 布置作业表单（多题目 + 学科选择）
  - `frontend/src/views/teacher/AssignmentsView.vue` — 作业列表概览
  - `frontend/src/views/student/AssignmentsView.vue` — 学生作业列表（含状态/提交/查看批改）
  - `frontend/src/views/student/SubmitView.vue` — 作业提交流程
  - `frontend/src/views/student/ResultView.vue` — 批改结果展示（逐题评分 + 评语）
  - `frontend/src/router/index.ts` — 路由表扩展（新增 6 条路由）
  - `frontend/src/layouts/TeacherLayout.vue` — 侧边栏导航扩展（班级管理/作业管理）
  - `feature_list.json` — 根据实际代码状态全面更新（12 个标记为 passing）
  - `backend/requirements.txt` — 添加 python-multipart 依赖
- 运行过的验证：
  - `cd backend && python -c "from main import app"` — 通过
  - `cd frontend && npm run build` — 通过（类型检查 + 构建成功）
- 已记录证据：构建成功日志
- 提交记录：待提交
- 更新过的文件或工件：参见以上列表
- 已知风险或未解决问题：
  - `init.ps1` 文件编码损坏（中文显示乱码 + 语法错误），需修复
  - 演示账户的班级和学科关联通过 seed.py 创建，但需要数据库运行
  - 学生提交流程图片使用模拟路径，需接入真实存储
- 下一步最佳动作：从 grading-001 开始构建批改引擎（PaddleOCR）

### Session 006 — grading-002 数学批改流水线（SymPy 表达式解析）

- 日期：2026-07-19
- 本轮目标：构建基于 SymPy 的数学批改流水线，支持表达式比较 + 步骤判分
- 已完成：
  - `backend/app/math_pipeline.py` — SymPy/LaTeX 表达式解析、数学等价性比较、步骤级判分
  - `backend/app/grade_assignment.py` — 学科路由调度器（取代旧 mock_grade），支持 math/chinese/english 分流
  - `backend/app/models.py` — Question 添加 answer 字段（标准答案）
  - `backend/init.sql` — 同步 answer 字段
  - `backend/app/routers/assignments.py` — CreateAssignmentRequest 支持 answer 字段
  - `backend/app/routers/submissions.py` — 改用 grade_submission 调度器，/mock-grade → /grade
  - `backend/requirements.txt` — 添加 sympy + latex2sympy2
  - `tests/test_math_pipeline.py` — 11 个单元测试，覆盖 Latex 解析、等价性比较、步骤判分
- 运行过的验证：
  - `python tests/test_math_pipeline.py` — 11/11 通过
  - `python -c "from app.grade_assignment import grade_submission"` — 导入通过
  - `cd frontend && npm run build` — 通过（未改动前端）
- 更新过的文件或工件：8 个文件 + 测试文件
- 已知风险或未解决问题：
  - latex2sympy 对复杂 LaTeX（如 \begin{equation}）可能报错，代码中有 fallback 机制
  - 步骤判分依赖 ; 和 \n 做切割，对连续文本步骤可能不准确
- 下一步最佳动作：grading-003 语文批改流水线（错别字检测 + 通顺度评分）

### Session 001 — Harness Engineering 基础设施引入

- 日期：2026-07-19
- 已完成：AGENTS.md、feature_list.json、claude-progress.md、init.ps1 等 8 个框架文件
- 运行过的验证：无（均为文档类文件）
