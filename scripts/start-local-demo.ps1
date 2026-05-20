param(
    [ValidateSet("stub", "real")]
    [string]$InferenceMode = "stub",

    [ValidateSet("small", "large")]
    [string]$RealModel = "small",

    [ValidateSet("deterministic", "sentence-transformers")]
    [string]$SemanticMode = "deterministic",

    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$coreEnvFile = if ($InferenceMode -eq "real") {
    if ($RealModel -eq "large") { ".env.demo-core.real" } else { ".env.demo-core.real-small" }
} else {
    ".env.demo-core"
}

$replicaEnvSuffix = if ($SemanticMode -eq "sentence-transformers") { ".semantic" } else { "" }

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
if ($InferenceMode -eq "real") {
    Write-Host "Real model profile: $RealModel"
}
Write-Host "Semantic mode: $SemanticMode"
Write-Host "Core env file: $coreEnvFile"

Start-DemoProject -EnvFile $coreEnvFile -ProjectName "cachemesh-core"
Start-DemoProject -EnvFile ".env.demo-replica-a$replicaEnvSuffix" -ProjectName "cachemesh-replica-a"
Start-DemoProject -EnvFile ".env.demo-replica-b$replicaEnvSuffix" -ProjectName "cachemesh-replica-b"
Start-DemoProject -EnvFile ".env.demo-replica-c$replicaEnvSuffix" -ProjectName "cachemesh-replica-c"

Write-Host ""
Write-Host "Local demo containers:"
docker ps --filter name=cachemesh --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"

Write-Host ""
Write-Host "Next checks:"
Write-Host "  curl.exe http://localhost:8100/members"
Write-Host "  curl.exe http://localhost:8050/health"
Write-Host "  Then POST a prompt to http://localhost:8000/cache/query"
