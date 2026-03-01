param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

function Remove-IfExists {
    param([string]$PathToRemove)
    if (Test-Path $PathToRemove) {
        Remove-Item -Force $PathToRemove
        Write-Host "Removed: $PathToRemove"
    }
}

if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Host "Uninstalling hotkey-transcriber from pipx..."
    $oldPythonIoEncoding = $env:PYTHONIOENCODING
    $oldPythonUtf8 = $env:PYTHONUTF8
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $env:PYTHONUTF8 = "1"
        pipx uninstall hotkey-transcriber *> $null
    } catch {
        Write-Host "pipx uninstall failed (likely console encoding issue), continuing cleanup."
    } finally {
        if ($null -ne $oldPythonIoEncoding) {
            $env:PYTHONIOENCODING = $oldPythonIoEncoding
        } else {
            Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
        }
        if ($null -ne $oldPythonUtf8) {
            $env:PYTHONUTF8 = $oldPythonUtf8
        } else {
            Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Host "pipx not found, skipping pipx uninstall."
}

Write-Host "Disabling autostart..."
$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if ($python) {
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $repoRoot "src"
        & $python -m hotkey_transcriber.autostart --set off --status | Out-Null
    } catch {
        Write-Host "Autostart cleanup via module failed, continuing."
    } finally {
        if ($null -ne $previousPythonPath) {
            $env:PYTHONPATH = $previousPythonPath
        } else {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        }
    }
}

$runPath = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
Remove-ItemProperty -Path $runPath -Name "HotkeyTranscriber" -ErrorAction SilentlyContinue

$programsDir = [Environment]::GetFolderPath("Programs")
Remove-IfExists (Join-Path $programsDir "Hotkey Transcriber.lnk")

$launcherDir = Join-Path $env:APPDATA "hotkey-transcriber"
Remove-IfExists (Join-Path $launcherDir "launch_hotkey_transcriber.vbs")
Remove-IfExists (Join-Path $launcherDir "hotkey-transcriber.ico")
if (Test-Path $launcherDir) {
    try {
        Remove-Item $launcherDir -Recurse -Force
    } catch {
        # Keep directory if still used by logs or other files.
    }
}

Write-Host "Uninstall complete."
