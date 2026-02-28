[CmdletBinding()]
param(
    [string]$Distro = "Ubuntu",
    [switch]$SkipRocmInstall,
    [switch]$SkipCTranslate2Build,
    [switch]$SkipWindowsAppInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Convert-WindowsPathToWslPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $drive = $resolved.Substring(0, 1).ToLowerInvariant()
    $tail = $resolved.Substring(2).Replace('\', '/')
    return "/mnt/$drive$tail"
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "wsl.exe not found. Install WSL first (`wsl --install`)."
}

$gpuNames = @(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)
$isAmd = $false
foreach ($name in $gpuNames) {
    if ($name -match "AMD|Radeon") {
        $isAmd = $true
        break
    }
}
if (-not $isAmd) {
    Write-Warning "No AMD GPU detected in Win32_VideoController. Continuing anyway."
}

if (-not (Test-IsAdmin)) {
    Write-Warning "Run this script from an elevated PowerShell for first-time WSL install."
}

$distroNames = @(wsl.exe -l -q 2>$null) | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if ($distroNames -notcontains $Distro) {
    Write-Host "Installing WSL distro '$Distro'..."
    wsl.exe --install -d $Distro
    Write-Host "WSL distro installation triggered. Reboot Windows if requested, then rerun this script."
    exit 0
}

$scriptWin = Join-Path $PSScriptRoot "wsl\setup_hotkey_transcriber_rocm.sh"
if (-not (Test-Path -LiteralPath $scriptWin)) {
    throw "Missing script: $scriptWin"
}

$scriptWsl = Convert-WindowsPathToWslPath -Path $scriptWin
$argsList = @()
if ($SkipRocmInstall) { $argsList += "--skip-rocm-install" }
if ($SkipCTranslate2Build) { $argsList += "--skip-ct2-build" }
$argString = ($argsList -join " ")

Write-Host "Running WSL setup script in '$Distro'..."
wsl.exe -d $Distro -- bash -lc "chmod +x '$scriptWsl' && '$scriptWsl' $argString"

if (-not $SkipWindowsAppInstall) {
    Write-Host "Installing/refreshing Windows app via pipx..."
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
        py -m pip install --user pipx
        py -m pipx ensurepath
        Write-Host "pipx installed. Restart PowerShell after this run if command is not yet available."
    }
    pipx install --force $repoRoot
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Start app with:"
Write-Host '  $env:HOTKEY_TRANSCRIBER_BACKEND="auto"'
Write-Host "  hotkey-transcriber"
