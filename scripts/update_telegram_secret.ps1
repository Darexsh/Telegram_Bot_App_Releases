param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Owner
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is not installed."
}

try {
    gh auth status | Out-Null
}
catch {
    Write-Error "Please run: gh auth login"
}

if (-not $env:NEW_TG_TOKEN) {
    $secureToken = Read-Host -Prompt "Enter new Telegram bot token" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    try {
        $env:NEW_TG_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

Write-Host "Scanning repositories for .github/workflows/release-telegram.yml ..."

$repos = gh repo list $Owner --limit 200 --json name --jq ".[].name"
foreach ($repo in $repos) {
    $checkCmd = "repos/$Owner/$repo/contents/.github/workflows/release-telegram.yml"
    gh api $checkCmd *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Updating TELEGRAM_BOT_TOKEN in $Owner/$repo"
        gh secret set TELEGRAM_BOT_TOKEN --repo "$Owner/$repo" --body "$env:NEW_TG_TOKEN"
    }
}

Write-Host "Done."
