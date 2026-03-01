param(
  [string]$OutputDir = "outputs/refactor_baseline"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$env:PYTHONIOENCODING = "utf-8"

if (!(Test-Path $OutputDir)) {
  New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $OutputDir "baseline_$timestamp.log"
$failedSteps = @()

function Invoke-Step {
  param(
    [string]$Name,
    [string]$Command
  )
  Write-Host "== $Name =="
  Add-Content -Path $logPath -Value "== $Name =="
  Add-Content -Path $logPath -Value "COMMAND: $Command"

  $tmpOut = [System.IO.Path]::GetTempFileName()
  $tmpErr = [System.IO.Path]::GetTempFileName()
  $proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $Command" -NoNewWindow -Wait -PassThru -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr

  if (Test-Path $tmpOut) {
    Get-Content $tmpOut | ForEach-Object {
      Write-Host $_
      Add-Content -Path $logPath -Value $_
    }
  }
  if (Test-Path $tmpErr) {
    Get-Content $tmpErr | ForEach-Object {
      Write-Host $_
      Add-Content -Path $logPath -Value $_
    }
  }
  Remove-Item $tmpOut -ErrorAction SilentlyContinue
  Remove-Item $tmpErr -ErrorAction SilentlyContinue

  $exitCode = $proc.ExitCode
  Add-Content -Path $logPath -Value "EXIT_CODE: $exitCode"
  if ($exitCode -ne 0) {
    $script:failedSteps += "$Name (exit $exitCode)"
  }

  Add-Content -Path $logPath -Value ""
}

Invoke-Step -Name "Context Check" -Command "python sdk/orchestrator/context_loader.py --mode check"
Invoke-Step -Name "Policy Guard" -Command "python sdk/orchestrator/policy_guard.py"
Invoke-Step -Name "Completion Status (Markdown)" -Command "python sdk/orchestrator/completion_status.py --format markdown --out docs/analysis/mekiki_completion_status.md"
Invoke-Step -Name "Hotspot Scan" -Command "python scripts/refactor/hotspot_scan.py --out docs/analysis/mekiki_hotspot_report.md --top 20"

if (Test-Path "OCR/scripts/audit_ids.py") {
  Invoke-Step -Name "Domain Check: audit_ids" -Command "python OCR/scripts/audit_ids.py --test --format=console"
}
if (Test-Path "OCR/scripts/audit_coords.py") {
  Invoke-Step -Name "Domain Check: audit_coords" -Command "python OCR/scripts/audit_coords.py --format=console"
}
if (Test-Path "OCR/scripts/audit_match_quality.py") {
  Invoke-Step -Name "Domain Check: audit_match_quality" -Command "python OCR/scripts/audit_match_quality.py --format=console"
}

Write-Host ""
Write-Host "Baseline snapshot complete."
Write-Host "Log: $logPath"
if ($failedSteps.Count -gt 0) {
  Write-Host "Failed steps:"
  $failedSteps | ForEach-Object { Write-Host "- $_" }
  exit 1
}
Write-Host "All steps passed."
