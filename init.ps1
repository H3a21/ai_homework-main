# init.ps1 — AI 智能批改作业系统 统一启动与验证入口
# 用法: .\init.ps1
# 设置 RUN_START=1 启动应用: $env:RUN_START=1; .\init.ps1

$ErrorActionPreference = "Stop"
$ROOT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT_DIR

Write-Host "==> 当前目录: $PWD"

Write-Host "==> 检查 Python 后端"
if (Test-Path "backend\main.py") {
    Write-Host "    ✓ main.py 存在"
    # 检查环境是否激活
    $envCheck = python -c "import fastapi" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    ✓ Python 依赖已安装"
    } else {
        Write-Host "    ⚠ Python 依赖未安装，运行: pip install -r backend/requirements.txt"
    }
} else {
    Write-Host "    ✗ backend\main.py 不存在"
}

Write-Host "==> 检查前端"
if (Test-Path "frontend\package.json") {
    Write-Host "    ✓ package.json 存在"
    if (Test-Path "frontend\node_modules") {
        Write-Host "    ✓ node_modules 存在"
    } else {
        Write-Host "    ⚠ node_modules 不存在，运行: cd frontend && npm install"
    }
} else {
    Write-Host "    ✗ frontend\package.json 不存在"
}

Write-Host "==> 检查 Docker 编排"
if (Test-Path "docker-compose.yml") {
    Write-Host "    ✓ docker-compose.yml 存在"
} else {
    Write-Host "    ✗ docker-compose.yml 不存在"
}

Write-Host "==> 检查 Harness 文件"
$harnessFiles = @("AGENTS.md", "feature_list.json", "claude-progress.md", "init.ps1")
foreach ($file in $harnessFiles) {
    if (Test-Path $file) {
        Write-Host "    ✓ $file 存在"
    } else {
        Write-Host "    ✗ $file 不存在"
    }
}

Write-Host "==> 基础验证完成"
Write-Host ""
Write-Host "启动命令:"
Write-Host "  后端: conda activate fastapi && uvicorn backend.main:app --reload --port 8000"
Write-Host "  前端: cd frontend && npm run dev"
Write-Host "  完整: docker compose up -d --build"
Write-Host ""
Write-Host "健康检查: http://localhost:8000/api/health"

if ($env:RUN_START -eq "1") {
    Write-Host "==> 启动应用 (RUN_START=1)"
    Write-Host "请手动启动服务，参考上方命令"
}
