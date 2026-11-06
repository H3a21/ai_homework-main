$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

docker compose up -d --build mysql-backup
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build and start mysql-backup"
}

$healthy = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    $health = docker inspect --format "{{.State.Health.Status}}" ai-homework-mysql-backup 2>$null
    if ($LASTEXITCODE -eq 0 -and $health -eq "healthy") {
        $healthy = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    docker compose logs --no-color --tail 100 mysql-backup
    throw "mysql-backup did not become healthy"
}

Start-Sleep -Seconds 1
$backupOutput = docker compose exec -T mysql-backup /usr/local/bin/backup.sh once 2>&1
if ($LASTEXITCODE -ne 0) {
    $backupOutput | Write-Output
    throw "On-demand MySQL backup failed"
}
$backupText = $backupOutput -join "`n"
$match = [regex]::Match(
    $backupText,
    "BACKUP_SUCCESS file=(full_[0-9]{8}_[0-9]{6}[.]sql[.]gz)"
)
if (-not $match.Success) {
    $backupOutput | Write-Output
    throw "Backup output did not contain a valid archive filename"
}
$filename = $match.Groups[1].Value

docker compose exec -T mysql-backup mc stat `
    "backup-minio/ai-homework-backups/mysql/$filename" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Backup archive is missing from MinIO"
}
docker compose exec -T mysql-backup mc stat `
    "backup-minio/ai-homework-backups/mysql/$filename.sha256" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Backup checksum is missing from MinIO"
}

$verifyOutput = docker compose exec -T mysql-backup `
    /usr/local/bin/restore.sh verify $filename 2>&1
if ($LASTEXITCODE -ne 0) {
    $verifyOutput | Write-Output
    throw "MinIO restore verification failed"
}
$verifyText = $verifyOutput -join "`n"
if ($verifyText -notmatch "RESTORE_VERIFY_SUCCESS.*tables=14.*source=minio.*cleanup=confirmed") {
    $verifyOutput | Write-Output
    throw "Restore verification did not confirm the expected schema"
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$safetyOutput = docker compose exec -T mysql-backup `
    /usr/local/bin/restore.sh restore $filename ai_homework 2>&1
$safetyExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
$safetyText = $safetyOutput -join "`n"
if ($safetyExitCode -eq 0) {
    throw "Restore unexpectedly allowed the primary database to be overwritten"
}
if ($safetyText -notmatch "refusing to overwrite primary database") {
    $safetyOutput | Write-Output
    throw "Restore failed without the expected primary-database safety guard"
}

Write-Output "PASS backup=$filename, MinIO checksum, isolated restore, cleanup, and overwrite guard"
