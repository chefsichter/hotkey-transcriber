param(
    [ValidateSet("ask", "on", "off")]
    [string]$Autostart = "ask"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py"
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
    }
    throw "Python launcher not found. Install Python first."
}

function Get-HotkeyTranscriberExecutable {
    $cmd = Get-Command hotkey-transcriber -ErrorAction SilentlyContinue
    if ($cmd -and (Test-Path $cmd.Source)) {
        return $cmd.Source
    }

    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\\bin\\hotkey-transcriber.exe"),
        (Join-Path $env:USERPROFILE ".local\\bin\\hotkey-transcriber")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Could not find hotkey-transcriber executable after install."
}

function New-StartMenuShortcut {
    $exePath = Get-HotkeyTranscriberExecutable
    $programsDir = [Environment]::GetFolderPath("Programs")
    $shortcutPath = Join-Path $programsDir "Hotkey Transcriber.lnk"

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $exePath
    $shortcut.WorkingDirectory = Split-Path -Parent $exePath
    $shortcut.Description = "Hotkey Transcriber (Live dictation tray app)"
    $shortcut.Save()

    Write-Host "Startmenü-Verknüpfung erstellt: $shortcutPath"
}

if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
    $python = Get-PythonCommand
    Write-Host "pipx not found - installing with $python..."
    & $python -m pip install --user pipx
    & $python -m pipx ensurepath
    Write-Host "pipx installed. Restart PowerShell if command resolution still fails."
}

Write-Host "Installing hotkey-transcriber with pipx..."
pipx install --force $repoRoot
New-StartMenuShortcut

if ($Autostart -eq "ask") {
    $answer = Read-Host "Autostart aktivieren? (j/n)"
    if ($answer -match "^(j|ja|y|yes)$") {
        $Autostart = "on"
    } else {
        $Autostart = "off"
    }
}

$python = Get-PythonCommand
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $repoRoot "src"
    if ($Autostart -eq "on") {
        & $python -m hotkey_transcriber.autostart --set on --status
    } else {
        & $python -m hotkey_transcriber.autostart --set off --status
    }
} finally {
    if ($null -ne $previousPythonPath) {
        $env:PYTHONPATH = $previousPythonPath
    } else {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
}

Write-Host "Installation abgeschlossen."
