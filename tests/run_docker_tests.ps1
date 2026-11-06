$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:RUN_TESTCONTAINERS = "1"
python -m pytest tests/test_testcontainers_smoke.py -m integration -q
if ($LASTEXITCODE -ne 0) {
    throw "Testcontainers smoke test failed"
}

& (Join-Path $PSScriptRoot "integration_mysql_backup.ps1")

$integrationScripts = @(
    "integration_submission_upload.py",
    "integration_realtime_grading.py",
    "integration_grading_batch.py",
    "integration_celery_grading.py",
    "integration_knowledge_profile.py",
    "integration_learning_reports.py"
)

foreach ($script in $integrationScripts) {
    $source = Join-Path "tests" $script
    $target = "/tmp/$script"
    docker compose cp $source "backend:$target"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy $script into backend container"
    }
    docker compose exec -T -e PYTHONPATH=/app backend python $target
    if ($LASTEXITCODE -ne 0) {
        throw "$script failed"
    }
}

Write-Output "All Docker integration checks passed."
