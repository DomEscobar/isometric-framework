param([switch]$CheckOnly, [switch]$Update)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv before running this setup.'
}
$taskScript = Join-Path $PSScriptRoot 'deploy.py'
$taskArgs = @('run', '--script', $taskScript)
if ($CheckOnly) { $taskArgs += '--check' }
if ($Update) { $taskArgs += '--update' }
& uv @taskArgs
if ($LASTEXITCODE -ne 0) { throw 'SAM 3 Space setup did not complete. See the sanitized message above.' }
