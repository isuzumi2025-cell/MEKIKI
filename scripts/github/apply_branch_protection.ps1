param(
  [string]$Branch = "main",
  [string]$Owner = "",
  [string]$Repo = "",
  [string]$Token = "",
  [int]$RequiredApprovals = 1,
  [switch]$EnforceAdmins,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-GitHubOwnerRepoFromRemote {
  $remoteUrl = git remote get-url origin 2>$null
  if (-not $remoteUrl) {
    throw "Could not read origin remote URL."
  }

  $patterns = @(
    "github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(\.git)?$",
    "github\.com/(?<owner>[^/]+)/(?<repo>[^/.]+)(\.git)?$"
  )

  foreach ($p in $patterns) {
    $m = [regex]::Match($remoteUrl, $p)
    if ($m.Success) {
      return @{
        Owner = $m.Groups["owner"].Value
        Repo = $m.Groups["repo"].Value
      }
    }
  }

  throw "Could not parse GitHub owner/repo from remote URL: $remoteUrl"
}

function Get-Token {
  param([string]$Explicit)
  if ($Explicit) { return $Explicit }
  if ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN }
  if ($env:GH_TOKEN) { return $env:GH_TOKEN }

  try {
    $credentialInput = "protocol=https`nhost=github.com`n`n"
    $credentialOutput = $credentialInput | git credential fill 2>$null
    if ($credentialOutput) {
      foreach ($line in ($credentialOutput -split "`n")) {
        if ($line -like "password=*") {
          $pwd = $line.Substring("password=".Length).Trim()
          if ($pwd) { return $pwd }
        }
      }
    }
  } catch {
    # fall through to error
  }

  throw "No token found. Set -Token or GITHUB_TOKEN/GH_TOKEN, or sign in via git credential helper."
}

if (-not $Owner -or -not $Repo) {
  $parsed = Get-GitHubOwnerRepoFromRemote
  if (-not $Owner) { $Owner = $parsed.Owner }
  if (-not $Repo) { $Repo = $parsed.Repo }
}
$enforceAdminsValue = [bool]$EnforceAdmins

$payload = @{
  required_status_checks = @{
    strict   = $true
    contexts = @(
      "contract-check",
      "governance-check"
    )
  }
  enforce_admins = $enforceAdminsValue
  required_pull_request_reviews = @{
    dismiss_stale_reviews           = $true
    require_code_owner_reviews      = $false
    required_approving_review_count = $RequiredApprovals
  }
  restrictions = $null
  allow_force_pushes = $false
  allow_deletions = $false
  required_conversation_resolution = $true
}

$json = $payload | ConvertTo-Json -Depth 10
$uri = "https://api.github.com/repos/$Owner/$Repo/branches/$Branch/protection"

Write-Host "Target repo: $Owner/$Repo"
Write-Host "Target branch: $Branch"
Write-Host "Required checks: contract-check, governance-check"
Write-Host "Required approvals: $RequiredApprovals"
Write-Host "Enforce admins: $enforceAdminsValue"

if ($DryRun) {
  Write-Host "DryRun enabled. Request payload:"
  Write-Output $json
  exit 0
}

$token = Get-Token -Explicit $Token

$headers = @{
  Authorization = "Bearer $token"
  Accept        = "application/vnd.github+json"
  "X-GitHub-Api-Version" = "2022-11-28"
}

$response = Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $json -ContentType "application/json"
Write-Host "Branch protection applied successfully."
if ($response.required_status_checks) {
  Write-Host "strict: $($response.required_status_checks.strict)"
  Write-Host "contexts: $($response.required_status_checks.contexts -join ', ')"
}
