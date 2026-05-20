$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

docker compose -p cachemesh-core down -v --remove-orphans
docker compose -p cachemesh-replica-a down -v --remove-orphans
docker compose -p cachemesh-replica-b down -v --remove-orphans
docker compose -p cachemesh-replica-c down -v --remove-orphans

Write-Host "CacheMesh local demo containers stopped."
