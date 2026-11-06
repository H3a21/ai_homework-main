# AGENTS.md — AI 智能批改作业系统

你正在一个面向 AI Agent 的长时实现工作仓库中工作。优先保证可靠完成、跨会话连续性和显式验证。

## 项目概览

视源股份 AI 应用赛道项目 — 多学科 AI 智能作业批改系统。支持数学/语文/英语作业的自动批改、个性化评语生成和学情分析。

## 技术栈

- **后端**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), MySQL 8.0, Celery, RabbitMQ, Redis
- **前端**: Vue 3 + TypeScript, Vite, Pinia, Vue Router
- **AI/ML**: PaddleOCR, SymPy, HuggingFace Transformers, Qwen/OpenAI API
- **基础设施**: Docker Compose, Nginx, Prometheus/Grafana, MinIO

## 开工流程

每轮会话开始时，严格按以下顺序执行：

1. 用 `pwd` 确认当前在仓库根目录 `ai_homework`
2. 读取 `claude-progress.md`，了解最新已验证状态和下一步
3. 读取 `feature_list.json`，选择优先级最高的未完成功能
4. 用 `git log --oneline -5` 查看最近提交
5. 运行 `.\init.ps1`（Windows PowerShell）
6. 检查基础验证路径是否已损坏（后端启动、前端构建）

如果基础验证一开始就失败，先修基础状态，不要在坏的起点上继续叠新功能。

## 工作规则

- **一次只做一个功能** — 同一时间只能有一个 `in_progress` 的功能
- **不要提前宣告完成** — 没有可运行的验证证据时，不要声称功能完成
- **不要削弱验证** — 不要为了"看起来完成"而删除、跳过或削弱测试
- **以仓库内文件为唯一事实来源** — 优先依赖 `feature_list.json`、`claude-progress.md` 等持久化文件，而不是聊天记录
- **不要范围蔓延** — 除非为了消除当前 blocker 的窄范围修复，否则不要扩大到其他功能

## 目录结构

```
ai_homework/
├── backend/           # FastAPI 后端
│   ├── main.py        # 应用入口
│   ├── database.py    # SQLAlchemy 引擎
│   ├── init.sql       # 数据库初始化脚本
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/          # Vue 3 前端
│   ├── src/           # 源码
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml # Docker 编排
├── AGENTS.md          # ← 本文件（Agent 指令）
├── feature_list.json  # 功能状态追踪
├── claude-progress.md # 会话进度日志
└── init.ps1           # 统一启动与验证入口
```

## 验证命令

```
后端验证:
  cd backend && python -c "from main import app; print('OK')"
  conda activate fastapi && uvicorn backend.main:app --port 8000  # 启动后访问 /api/health

前端验证:
  cd frontend && npm install && npm run build
  cd frontend && npm run dev

完整启动:
  docker compose up -d --build
  前端: http://localhost
  后端: http://localhost:8000
  健康检查: http://localhost:8000/api/health
```

## 完成定义

一个功能只有在以下条件都满足时才算完成：

- 目标行为已经实现（代码已编写并可通过功能验证）
- 要求的验证真的跑过且有通过证据
- 证据记录在 `feature_list.json` 或 `claude-progress.md`
- 仓库仍然能按标准启动路径重新开始工作

## 收尾流程

结束会话前必须按顺序执行：

1. 更新 `claude-progress.md` — 记录本轮完成内容、验证结果、风险
2. 更新 `feature_list.json` — 将功能状态改到正确状态
3. 记录仍未解决的风险或 blocker
4. 在工作处于安全状态后，用清晰的提交信息提交
5. 保证下一轮会话可以直接运行 `.\init.ps1`
