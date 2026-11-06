$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runId = ([guid]::NewGuid().ToString("N").Substring(0, 8)).ToLowerInvariant()
$fixtureTarget = "/tmp/browser_e2e_fixture.py"
$setupComplete = $false

Set-Location $repoRoot
docker compose cp "tests/browser_e2e_fixture.py" "backend:$fixtureTarget"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy browser E2E fixture into backend container"
}

try {
    docker compose exec -T -e PYTHONPATH=/app backend python $fixtureTarget setup $runId
    if ($LASTEXITCODE -ne 0) {
        throw "Browser E2E fixture setup failed"
    }
    $setupComplete = $true

    $env:DOCKER_E2E_RUN_ID = $runId
    Push-Location (Join-Path $repoRoot "frontend")
    try {
        npm.cmd run test:e2e:docker
        if ($LASTEXITCODE -ne 0) {
            throw "Docker browser E2E tests failed"
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item Env:DOCKER_E2E_RUN_ID -ErrorAction SilentlyContinue
    if ($setupComplete) {
        Set-Location $repoRoot
        docker compose exec -T -e PYTHONPATH=/app backend python $fixtureTarget cleanup $runId
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Browser E2E fixture cleanup failed for run $runId"
        }
    }
}

Write-Output "All Docker browser E2E workflows passed."
