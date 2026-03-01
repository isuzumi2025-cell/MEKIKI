param(
  [string]$Branch = "main",
  [string]$Owner = "",
  [string]$Repo = "",
  [string]$Token = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-GitHubOwnerRepoFromRemote {
  $remoteUrl = git remote get-url origin 2>$null
  if (-not $remoteUrl) {
    throw "Could not read origin remote URL."
  }

  $m = [regex]::Match($remoteUrl, "github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(\.git)?$")
  if (-not $m.Success) {
    throw "Could not parse GitHub owner/repo from remote URL: $remoteUrl"
  }

  return @{
    Owner = $m.Groups["owner"].Value
    Repo = $m.Groups["repo"].Value
  }
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

$token = Get-Token -Explicit $Token
$uri = "https://api.github.com/repos/$Owner/$Repo/branches/$Branch/protection"

$headers = @{
  Authorization = "Bearer $token"
  Accept        = "application/vnd.github+json"
  "X-GitHub-Api-Version" = "2022-11-28"
}

$response = Invoke-RestMethod -Uri $uri -Method Get -Headers $headers
$response | ConvertTo-Json -Depth 20
