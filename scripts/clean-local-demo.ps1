param(
    [switch]$PruneDockerSystem
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$projects = @(
    "cachemesh-core",
    "cachemesh-replica-a",
    "cachemesh-replica-b",
    "cachemesh-replica-c"
)

foreach ($project in $projects) {
    docker compose -p $project down --volumes --remove-orphans
}

$statePaths = @(
    ".docker\demo-replica-a",
    ".docker\demo-replica-b",
    ".docker\demo-replica-c",
    ".docker\qdrant"
)

foreach ($relativePath in $statePaths) {
    $path = Join-Path $repoRoot $relativePath
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
        Write-Host "Removed $relativePath"
    }
}

if ($PruneDockerSystem) {
    docker system prune -a --volumes -f
}

Write-Host "CacheMesh local demo containers and persisted demo state cleaned."
