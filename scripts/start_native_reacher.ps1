param([switch]$Prepare, [switch]$Build)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsRoot = Join-Path $projectRoot 'data/tools/reacher-native'
$previousTools = [Environment]::GetEnvironmentVariable('NATIVE_REACHER_TOOLS', 'Process')
$previousCompiler = [Environment]::GetEnvironmentVariable('NATIVE_REACHER_COMPILER', 'Process')
$previousTarget = [Environment]::GetEnvironmentVariable('NATIVE_REACHER_TARGET', 'Process')
$previousSDK = [Environment]::GetEnvironmentVariable('NATIVE_REACHER_SDK', 'Process')
try {
    if ($toolsRoot.Contains(' ')) {
        # A junction provides a short spelling of the same workspace files.
        # Existing aliases must point here; another workspace is never replaced.
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $hash = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($projectRoot))).Replace('-', '').Substring(0, 12).ToLowerInvariant()
        } finally { $sha.Dispose() }
        $aliasParent = Join-Path $env:LOCALAPPDATA 'OutreachWorkbench'
        $aliasPath = Join-Path $aliasParent "reacher-$hash"
        if ($aliasPath.Contains(' ')) { throw 'LocalAppData also has spaces; use a space-free native tools location or the Linux/Docker verifier profile.' }
        New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
        New-Item -ItemType Directory -Path $aliasParent -Force | Out-Null
        if (Test-Path -LiteralPath $aliasPath) {
            $alias = Get-Item -LiteralPath $aliasPath -Force
            if ($alias.LinkType -ne 'Junction' -or [string]$alias.Target -ne $toolsRoot) {
                throw 'Existing native build alias does not point to this workspace; no files changed.'
            }
        } else {
            New-Item -ItemType Junction -Path $aliasPath -Target $toolsRoot | Out-Null
        }
        $env:NATIVE_REACHER_TOOLS = $aliasPath
        # GCC resolves junctions internally; its own files must physically live
        # at a space-free path. This copy is isolated to the current user/project.
        $compilerParent = Join-Path $aliasParent "compiler-$hash"
        $compilerPath = Join-Path $compilerParent 'mingw64'
        if (-not (Test-Path -LiteralPath (Join-Path $compilerPath 'bin/gcc.exe'))) {
            $downloadedCompiler = Join-Path $toolsRoot 'mingw64'
            if (Test-Path -LiteralPath $downloadedCompiler) {
                New-Item -ItemType Directory -Path $compilerParent -Force | Out-Null
                Copy-Item -LiteralPath $downloadedCompiler -Destination $compilerParent -Recurse
            }
        }
        $env:NATIVE_REACHER_COMPILER = $compilerPath
        $env:NATIVE_REACHER_TARGET = Join-Path $aliasParent "build-$hash"
        $env:NATIVE_REACHER_SDK = Join-Path $aliasParent "sdk-$hash"
    } else {
        $env:NATIVE_REACHER_TOOLS = $toolsRoot
        $env:NATIVE_REACHER_COMPILER = Join-Path $toolsRoot 'mingw64'
        $env:NATIVE_REACHER_TARGET = Join-Path $toolsRoot 'source/target'
        $env:NATIVE_REACHER_SDK = Join-Path $toolsRoot 'openssl-sdk'
    }
    $pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
    $arguments = @((Join-Path $PSScriptRoot 'start_native_reacher.py'))
    if ($Prepare) { $arguments += '--prepare' }
    if ($Build) { $arguments += '--build' }
    Push-Location -LiteralPath $projectRoot
    try {
        & $pythonPath @arguments
        if ($LASTEXITCODE -ne 0) { throw 'Native Reacher preparation/build/start failed; see its local report/log.' }
    } finally { Pop-Location }
} finally {
    [Environment]::SetEnvironmentVariable('NATIVE_REACHER_TOOLS', $previousTools, 'Process')
    [Environment]::SetEnvironmentVariable('NATIVE_REACHER_COMPILER', $previousCompiler, 'Process')
    [Environment]::SetEnvironmentVariable('NATIVE_REACHER_TARGET', $previousTarget, 'Process')
    [Environment]::SetEnvironmentVariable('NATIVE_REACHER_SDK', $previousSDK, 'Process')
}
