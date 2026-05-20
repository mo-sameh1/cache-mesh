param(
    [ValidateSet("stub", "real")]
    [string]$InferenceMode = "stub",

    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$coreEnvFile = if ($InferenceMode -eq "real") { ".env.demo-core.real" } else { ".env.demo-core" }

function Start-DemoProject {
    param(
        [string]$EnvFile,
        [string]$ProjectName
    )

    $args = @("compose", "--env-file", $EnvFile, "-p", $ProjectName, "up", "-d")
    if (-not $NoBuild) {
        $args += "--build"
    }

    & docker @args
}

Write-Host "Starting CacheMesh local demo from $repoRoot"
Write-Host "Inference mode: $InferenceMode"
Write-Host "Core env file: $coreEnvFile"

Start-DemoProject -EnvFile $coreEnvFile -ProjectName "cachemesh-core"
Start-DemoProject -EnvFile ".env.demo-replica-a" -ProjectName "cachemesh-replica-a"
Start-DemoProject -EnvFile ".env.demo-replica-b" -ProjectName "cachemesh-replica-b"
Start-DemoProject -EnvFile ".env.demo-replica-c" -ProjectName "cachemesh-replica-c"

Write-Host ""
Write-Host "Local demo containers:"
docker ps --filter name=cachemesh --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"

Write-Host ""
Write-Host "Next checks:"
Write-Host "  curl.exe http://localhost:8100/members"
Write-Host "  curl.exe http://localhost:8050/health"
Write-Host "  Then POST a prompt to http://localhost:8000/cache/query"
