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

function Get-ShortcutIconPath {
    $iconDir = Join-Path $env:APPDATA "hotkey-transcriber"
    New-Item -ItemType Directory -Force -Path $iconDir | Out-Null
    return Join-Path $iconDir "hotkey-transcriber.ico"
}

function Ensure-ShortcutIcon {
    $iconPath = Get-ShortcutIconPath
    $pngPath = Join-Path $repoRoot "src\\hotkey_transcriber\\resources\\icon\\microphone.png"

    if (Test-Path $pngPath) {
        Add-Type -AssemblyName System.Drawing
        $bitmap = [System.Drawing.Bitmap]::FromFile($pngPath)
        try {
            $icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
            try {
                $stream = [System.IO.File]::Open($iconPath, [System.IO.FileMode]::Create)
                try {
                    $icon.Save($stream)
                } finally {
                    $stream.Close()
                }
            } finally {
                $icon.Dispose()
            }
        } finally {
            $bitmap.Dispose()
        }
    }

    if (Test-Path $iconPath) {
        return $iconPath
    }

    return Get-HotkeyTranscriberExecutable
}

function Get-LauncherScriptPath {
    $launcherDir = Join-Path $env:APPDATA "hotkey-transcriber"
    New-Item -ItemType Directory -Force -Path $launcherDir | Out-Null
    return Join-Path $launcherDir "launch_hotkey_transcriber.vbs"
}

function New-HiddenLauncherScript {
    $exePath = Get-HotkeyTranscriberExecutable
    $launcherPath = Get-LauncherScriptPath
    $escaped = $exePath.Replace('"', '""')
    $content = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """$escaped""", 0, False
"@
    Set-Content -Path $launcherPath -Value $content -Encoding UTF8
    return $launcherPath
}

function New-StartMenuShortcut {
    $launcherPath = New-HiddenLauncherScript
    $iconPath = Ensure-ShortcutIcon
    $programsDir = [Environment]::GetFolderPath("Programs")
    $shortcutPath = Join-Path $programsDir "Hotkey Transcriber.lnk"

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "wscript.exe"
    $shortcut.Arguments = "`"$launcherPath`""
    $shortcut.WorkingDirectory = Split-Path -Parent $launcherPath
    $shortcut.Description = "Hotkey Transcriber (tray app)"
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.Save()

    Write-Host "Startmenü-Verknüpfung erstellt: $shortcutPath (ohne Terminalfenster)"
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
